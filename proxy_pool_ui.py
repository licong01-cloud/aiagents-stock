import os
import json
import streamlit as st

from config_manager import config_manager
from network_optimizer import network_optimizer


def _bool_to_str(v: bool) -> str:
    return "true" if v else "false"


def display_proxy_pool_manager():
    st.subheader("🌐 代理池与网络优化管理")

    # 概览
    status = network_optimizer.get_network_status()
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        st.metric("启用代理", "是" if status.get("use_proxy") else "否")
    with col_b:
        st.metric("动态源数量", status.get("dynamic_enabled") and len(network_optimizer.dynamic_sources) or 0)
    with col_c:
        st.metric("缓存代理数", status.get("dynamic_cache_size", 0))
    with col_d:
        st.metric("上次刷新", str(int(status.get("last_refresh", 0))))

    st.markdown("---")

    # 全局设置
    st.markdown("### ⚙️ 全局设置")
    env = config_manager.read_env()

    col1, col2 = st.columns(2)
    with col1:
        use_proxy = st.checkbox("启用代理", value=(env.get("USE_PROXY", "false") == "true"))
        proxypool_enabled = st.checkbox("启用动态代理池", value=(env.get("PROXYPOOL_ENABLED", "false") == "true"))
        refresh_min = st.text_input("刷新间隔(分钟)", value=env.get("PROXY_REFRESH_INTERVAL_MIN", "10"))
    with col2:
        base_url = st.text_input("代理池Base URL", value=env.get("PROXYPOOL_BASE_URL", ""))
        auth_type = st.selectbox("鉴权方式", options=["token", "basic", "urlparam"], index=["token","basic","urlparam"].index(env.get("PROXYPOOL_AUTH_TYPE", "token")))
        if auth_type in ("token", "urlparam"):
            token_val = st.text_input("Token", value=env.get("PROXYPOOL_TOKEN", ""), type="password")
        else:
            colu, colp = st.columns(2)
            with colu:
                username_val = st.text_input("用户名", value=env.get("PROXYPOOL_USERNAME", ""))
            with colp:
                password_val = st.text_input("密码", value=env.get("PROXYPOOL_PASSWORD", ""), type="password")

    col_s, col_t = st.columns(2)
    with col_s:
        if st.button("💾 保存配置", key="proxy_save_env"):
            env["USE_PROXY"] = _bool_to_str(use_proxy)
            env["PROXYPOOL_ENABLED"] = _bool_to_str(proxypool_enabled)
            env["PROXY_REFRESH_INTERVAL_MIN"] = str(refresh_min)
            env["PROXYPOOL_BASE_URL"] = base_url
            env["PROXYPOOL_AUTH_TYPE"] = auth_type
            if auth_type in ("token", "urlparam"):
                env["PROXYPOOL_TOKEN"] = token_val
                env["PROXYPOOL_USERNAME"] = ""
                env["PROXYPOOL_PASSWORD"] = ""
            else:
                env["PROXYPOOL_USERNAME"] = username_val
                env["PROXYPOOL_PASSWORD"] = password_val
                env["PROXYPOOL_TOKEN"] = ""

            if config_manager.write_env(env):
                st.success("✅ 已保存到 .env，请重启或重新加载使配置生效")
                try:
                    config_manager.reload_config()
                    st.info("已重新加载配置")
                except Exception as e:
                    st.warning(f"重新加载失败: {e}")
            else:
                st.error("❌ 保存失败")
    with col_t:
        if st.button("🌐 测试网络连通", key="proxy_test_network"):
            ok = network_optimizer.test_network_connection()
            if ok:
                st.success("✅ 网络连通正常")
            else:
                st.warning("⚠️ 网络不可达或较慢")

    st.markdown("---")
    st.markdown("### 🔄 动态代理池源")

    # 新增/编辑动态源
    with st.expander("新增动态源"):
        name_new = st.text_input("名称", value="")
        base_new = st.text_input("Base URL", value="")
        auth_new = st.selectbox("鉴权方式", options=["token","basic","urlparam"], index=0, key="auth_new")
        param_key = st.text_input("URL参数名(仅urlparam)", value="token", key="param_key_new")
        params_json = st.text_area("额外参数(JSON)", value="{}", key="params_new")
        enabled_new = st.checkbox("启用", value=True, key="enabled_new")
        if st.button("➕ 添加动态源"):
            try:
                params = json.loads(params_json) if params_json.strip() else {}
            except Exception as e:
                st.error(f"参数JSON无效: {e}")
                params = {}
            auth = {"type": auth_new}
            if auth_new == "urlparam":
                auth["param_key"] = param_key
            ok = network_optimizer.add_dynamic_proxy_source(name_new, base_new, auth, params=params, enabled=enabled_new)
            if ok:
                st.success("✅ 已添加动态源")
            else:
                st.error("❌ 添加失败")

    # 列表与操作
    sources = list(network_optimizer.dynamic_sources.values())
    if not sources:
        st.info("暂无动态源")
    else:
        for src in sources:
            with st.expander(f"源：{src.get('name')}"):
                st.write({k: v for k, v in src.items() if k != 'auth'})
                colx, coly, colz = st.columns(3)
                with colx:
                    if st.button("🧪 获取并测试", key=f"test_{src.get('name')}"):
                        p = network_optimizer.get_dynamic_proxy_from_source(src.get("name"))
                        if p and network_optimizer.test_proxy_fast({"proxy": p}):
                            st.success(f"✅ {p}")
                        else:
                            st.warning("⚠️ 获取或连通失败")
                with coly:
                    # 启用/禁用切换
                    current = src.get("enabled", True)
                    if st.button("切换启用/禁用", key=f"toggle_{src.get('name')}"):
                        src["enabled"] = not current
                        try:
                            # 直接保存配置（非敏感项）
                            network_optimizer._save_config()  # noqa: E402 (内部使用)
                            st.success("已切换状态")
                        except Exception as e:
                            st.error(f"保存失败: {e}")
                with colz:
                    if st.button("🗑️ 删除", key=f"del_{src.get('name')}"):
                        try:
                            if src.get("name") in network_optimizer.dynamic_sources:
                                del network_optimizer.dynamic_sources[src.get("name")]
                                network_optimizer._save_config()
                                st.success("已删除该源")
                        except Exception as e:
                            st.error(f"删除失败: {e}")

    st.markdown("---")
    st.markdown("### 📚 静态代理（可选）")
    # 简版静态代理管理
    static_list = network_optimizer.get_proxy_list()
    if static_list:
        for p in static_list:
            with st.expander(f"{p.get('name')} | prio={p.get('priority')} | {'启用' if p.get('enabled') else '禁用'}"):
                colp1, colp2, colp3, colp4 = st.columns(4)
                with colp1:
                    if st.button("测试", key=f"test_static_{p.get('name')}"):
                        ok = network_optimizer.test_proxy_fast(p)
                        st.write("✅ 可用" if ok else "❌ 不可用")
                with colp2:
                    if st.button("启用/禁用", key=f"toggle_static_{p.get('name')}"):
                        network_optimizer.toggle_proxy(p.get('name'), not p.get('enabled'))
                        st.success("已更新")
                with colp3:
                    new_prio = st.number_input("优先级", value=int(p.get('priority', 1)), step=1, key=f"prio_{p.get('name')}")
                    if st.button("保存优先级", key=f"save_prio_{p.get('name')}"):
                        network_optimizer.update_proxy_priority(p.get('name'), int(new_prio))
                        st.success("已保存")
                with colp4:
                    if st.button("删除", key=f"del_static_{p.get('name')}"):
                        network_optimizer.remove_proxy(p.get('name'))
                        st.success("已删除")

    with st.expander("➕ 新增静态代理"):
        n = st.text_input("名称", value="", key="static_name")
        proxy = st.text_input("代理地址", value="http://127.0.0.1:7890", key="static_proxy")
        pr = st.number_input("优先级", value=1, step=1, key="static_prio")
        en = st.checkbox("启用", value=True, key="static_enabled")
        if st.button("添加静态代理"):
            network_optimizer.add_proxy(n, {"proxy": proxy}, priority=int(pr), enabled=en)
            st.success("已添加")


