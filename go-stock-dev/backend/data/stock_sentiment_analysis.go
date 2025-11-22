package data

import (
	"bufio"
	"fmt"
	"go-stock/backend/logger"
	"os"
	"strings"

	"github.com/go-ego/gse"
)

// 金融情感词典，包含股票市场相关的专业词汇
var (
	seg gse.Segmenter

	// 正面金融词汇及其权重
	positiveFinanceWords = map[string]float64{
		"上涨": 2.0, "涨停": 3.0, "牛市": 3.0, "反弹": 2.0, "新高": 2.5,
		"利好": 2.5, "增持": 2.0, "买入": 2.0, "推荐": 1.5, "看多": 2.0,
		"盈利": 2.0, "增长": 2.0, "超预期": 2.5, "强劲": 1.5, "回升": 1.5,
		"复苏": 2.0, "突破": 2.0, "创新高": 3.0, "回暖": 1.5, "上扬": 1.5,
		"利好消息": 3.0, "收益增长": 2.5, "利润增长": 2.5, "业绩优异": 2.5,
		"潜力股": 2.0, "绩优股": 2.0, "强势": 1.5, "走高": 1.5, "攀升": 1.5,
		"大涨": 2.5, "飙升": 3.0, "井喷": 3.0, "爆发": 2.5, "暴涨": 3.0,
	}

	// 负面金融词汇及其权重
	negativeFinanceWords = map[string]float64{
		"下跌": 2.0, "跌停": 3.0, "熊市": 3.0, "回调": 1.5, "新低": 2.5,
		"利空": 2.5, "减持": 2.0, "卖出": 2.0, "看空": 2.0, "亏损": 2.5,
		"下滑": 2.0, "萎缩": 2.0, "不及预期": 2.5, "疲软": 1.5, "恶化": 2.0,
		"衰退": 2.0, "跌破": 2.0, "创新低": 3.0, "走弱": 1.5, "下挫": 1.5,
		"利空消息": 3.0, "收益下降": 2.5, "利润下滑": 2.5, "业绩不佳": 2.5,
		"垃圾股": 2.0, "风险股": 2.0, "弱势": 1.5, "走低": 1.5, "缩量": 2.5,
		"大跌": 2.5, "暴跌": 3.0, "崩盘": 3.0, "跳水": 3.0, "重挫": 3.0,
	}

	// 否定词，用于反转情感极性
	negationWords = map[string]struct{}{
		"不": {}, "没": {}, "无": {}, "非": {}, "未": {}, "别": {}, "勿": {},
	}

	// 程度副词，用于调整情感强度
	degreeWords = map[string]float64{
		"非常": 1.8, "极其": 2.2, "太": 1.8, "很": 1.5,
		"比较": 0.8, "稍微": 0.6, "有点": 0.7, "显著": 1.5,
		"大幅": 1.8, "急剧": 2.0, "轻微": 0.6, "小幅": 0.7,
	}

	// 转折词，用于识别情感转折
	transitionWords = map[string]struct{}{
		"但是": {}, "然而": {}, "不过": {}, "却": {}, "可是": {},
	}
)

func init() {
	// 加载默认词典
	err := seg.LoadDict()
	if err != nil {
		logger.SugaredLogger.Error(err.Error())
	}
}

// SentimentResult 情感分析结果类型
type SentimentResult struct {
	Score         float64       // 情感得分
	Category      SentimentType // 情感类别
	PositiveCount int           // 正面词数量
	NegativeCount int           // 负面词数量
	Description   string        // 情感描述
}

// SentimentType 情感类型枚举
type SentimentType int

const (
	Positive SentimentType = iota
	Negative
	Neutral
)

// AnalyzeSentiment 判断文本的情感
func AnalyzeSentiment(text string) SentimentResult {
	// 初始化得分
	score := 0.0
	positiveCount := 0
	negativeCount := 0

	// 分词（简单按单个字符分割）
	words := splitWords(text)

	// 检查文本是否包含转折词，并分割成两部分
	var transitionIndex int
	var hasTransition bool
	for i, word := range words {
		if _, ok := transitionWords[word]; ok {
			transitionIndex = i
			hasTransition = true
			break
		}
	}

	// 处理有转折的文本
	if hasTransition {
		// 转折前的部分
		preTransitionWords := words[:transitionIndex]
		preScore, prePos, preNeg := calculateScore(preTransitionWords)

		// 转折后的部分，权重加倍
		postTransitionWords := words[transitionIndex+1:]
		postScore, postPos, postNeg := calculateScore(postTransitionWords)
		postScore *= 1.5 // 转折后的情感更重要

		score = preScore + postScore
		positiveCount = prePos + postPos
		negativeCount = preNeg + postNeg
	} else {
		// 没有转折的文本
		score, positiveCount, negativeCount = calculateScore(words)
	}

	// 确定情感类别
	var category SentimentType
	switch {
	case score > 1.0:
		category = Positive
	case score < -1.0:
		category = Negative
	default:
		category = Neutral
	}

	return SentimentResult{
		Score:         score,
		Category:      category,
		PositiveCount: positiveCount,
		NegativeCount: negativeCount,
		Description:   GetSentimentDescription(category),
	}
}

// 计算情感得分
func calculateScore(words []string) (float64, int, int) {
	score := 0.0
	positiveCount := 0
	negativeCount := 0

	// 遍历每个词，计算情感得分
	for i, word := range words {
		// 首先检查是否为程度副词
		degree, isDegree := degreeWords[word]

		// 检查是否为否定词
		_, isNegation := negationWords[word]

		// 检查是否为金融正面词
		if posScore, isPositive := positiveFinanceWords[word]; isPositive {
			// 检查前一个词是否为否定词或程度副词
			if i > 0 {
				prevWord := words[i-1]
				if _, isNeg := negationWords[prevWord]; isNeg {
					score -= posScore
					negativeCount++
					continue
				}

				if deg, isDeg := degreeWords[prevWord]; isDeg {
					score += posScore * deg
					positiveCount++
					continue
				}
			}

			score += posScore
			positiveCount++
			continue
		}

		// 检查是否为金融负面词
		if negScore, isNegative := negativeFinanceWords[word]; isNegative {
			// 检查前一个词是否为否定词或程度副词
			if i > 0 {
				prevWord := words[i-1]
				if _, isNeg := negationWords[prevWord]; isNeg {
					score += negScore
					positiveCount++
					continue
				}

				if deg, isDeg := degreeWords[prevWord]; isDeg {
					score -= negScore * deg
					negativeCount++
					continue
				}
			}

			score -= negScore
			negativeCount++
			continue
		}

		// 处理程度副词（如果后面跟着情感词）
		if isDegree && i+1 < len(words) {
			nextWord := words[i+1]

			if posScore, isPositive := positiveFinanceWords[nextWord]; isPositive {
				score += posScore * degree
				positiveCount++
				continue
			}

			if negScore, isNegative := negativeFinanceWords[nextWord]; isNegative {
				score -= negScore * degree
				negativeCount++
				continue
			}
		}

		// 处理否定词（如果后面跟着情感词）
		if isNegation && i+1 < len(words) {
			nextWord := words[i+1]

			if posScore, isPositive := positiveFinanceWords[nextWord]; isPositive {
				score -= posScore
				negativeCount++
				continue
			}

			if negScore, isNegative := negativeFinanceWords[nextWord]; isNegative {
				score += negScore
				positiveCount++
				continue
			}
		}
	}

	return score, positiveCount, negativeCount
}

// 简单的分词函数，考虑了中文和英文
func splitWords(text string) []string {
	return seg.Cut(text, true)
}

// GetSentimentDescription 获取情感类别的文本描述
func GetSentimentDescription(category SentimentType) string {
	switch category {
	case Positive:
		return "看涨"
	case Negative:
		return "看跌"
	case Neutral:
		return "中性"
	default:
		return "未知"
	}
}

func main() {
	// 从命令行读取输入
	reader := bufio.NewReader(os.Stdin)
	fmt.Println("请输入要分析的股市相关文本（输入exit退出）：")

	for {
		fmt.Print("> ")
		text, err := reader.ReadString('\n')
		if err != nil {
			fmt.Println("读取输入时出错:", err)
			continue
		}

		// 去除换行符
		text = strings.TrimSpace(text)

		// 检查是否退出
		if text == "exit" {
			break
		}

		// 分析情感
		result := AnalyzeSentiment(text)

		// 输出结果
		fmt.Printf("情感分析结果: %s (得分: %.2f, 正面词:%d, 负面词:%d)\n",
			GetSentimentDescription(result.Category),
			result.Score,
			result.PositiveCount,
			result.NegativeCount)
	}
}
