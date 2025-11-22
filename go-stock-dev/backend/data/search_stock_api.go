package data

import (
	"encoding/json"
	"fmt"
	"go-stock/backend/logger"
	"time"

	"github.com/go-resty/resty/v2"
)

// @Author spark
// @Date 2025/6/28 21:02
// @Desc
// -----------------------------------------------------------------------------------
type SearchStockApi struct {
	words string
}

func NewSearchStockApi(words string) *SearchStockApi {
	return &SearchStockApi{words: words}
}
func (s SearchStockApi) SearchStock(pageSize int) map[string]any {
	url := "https://np-tjxg-g.eastmoney.com/api/smart-tag/stock/v3/pw/search-code"
	resp, err := resty.New().SetTimeout(time.Duration(30)*time.Second).R().
		SetHeader("Host", "np-tjxg-g.eastmoney.com").
		SetHeader("Origin", "https://xuangu.eastmoney.com").
		SetHeader("Referer", "https://xuangu.eastmoney.com/").
		SetHeader("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:145.0) Gecko/20100101 Firefox/145.0").
		SetHeader("Content-Type", "application/json").
		SetBody(fmt.Sprintf(`{
				"keyWord": "%s",
				"pageSize": %d,
				"pageNo": 1,
				"fingerprint": "02efa8944b1f90fbfe050e1e695a480d",
				"gids": [],
				"matchWord": "",
				"timestamp": "%d",
				"shareToGuba": false,
				"requestId": "RMd3Y76AJI98axPvdhdbKvbBDVwLlUK61761559950168",
				"needCorrect": true,
				"removedConditionIdList": [],
				"xcId": "xc0d61279aad33008260",
				"ownSelectAll": false,
				"dxInfo": [],
				"extraCondition": ""
				}`, s.words, pageSize, time.Now().Unix())).Post(url)
	if err != nil {
		logger.SugaredLogger.Errorf("SearchStock-err:%+v", err)
		return map[string]any{}
	}
	respMap := map[string]any{}
	json.Unmarshal(resp.Body(), &respMap)
	//logger.SugaredLogger.Infof("resp:%+v", respMap["data"])
	return respMap
}

func (s SearchStockApi) HotStrategy() map[string]any {
	url := fmt.Sprintf("https://np-ipick.eastmoney.com/recommend/stock/heat/ranking?count=20&trace=%d&client=web&biz=web_smart_tag", time.Now().Unix())
	resp, err := resty.New().SetTimeout(time.Duration(30)*time.Second).R().
		SetHeader("Host", "np-ipick.eastmoney.com").
		SetHeader("Origin", "https://xuangu.eastmoney.com").
		SetHeader("Referer", "https://xuangu.eastmoney.com/").
		SetHeader("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0").
		Get(url)
	if err != nil {
		logger.SugaredLogger.Errorf("HotStrategy-err:%+v", err)
		return map[string]any{}
	}
	respMap := map[string]any{}
	json.Unmarshal(resp.Body(), &respMap)
	return respMap
}
