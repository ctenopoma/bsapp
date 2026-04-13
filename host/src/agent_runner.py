import logging
import time
import urllib.request
import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from typing import Dict, Any, List

from .session_manager import session_manager, SessionMemory
from .models import MessageHistory, ThemeSummary, FullSessionResult, PatentItem, PatentAnalyzeRequest, PatentCompressRequest, PatentChunkedAnalyzeRequest
from .app_settings import get_settings, get_llm_config
import uuid as _uuid
from .workflow import (
    select_persona,
    build_agent_input,
    run_one_theme,
    run_full_session,
    summarize_theme,
)
from .workflow.patent import analyze_company, analyze_chunked, compress_patents
from .workflow.patent.stats import run_stats_with_configs, ProcessorRunConfig
from .workflow.patent.stats.runner import results_to_markdown, results_to_variables

logger = logging.getLogger("bsapp.llm")

# Temporary simple dictionary to hold job statuses
job_statuses: Dict[str, Dict[str, Any]] = {}


def _proxy_status(url: str) -> str:
    """URLがプロキシ経由になるか判定して文字列で返す。"""
    from urllib.parse import urlparse
    host = urlparse(url).hostname or url
    try:
        bypassed = urllib.request.proxy_bypass(host)
    except Exception:
        bypassed = False
    if bypassed:
        return "BYPASS (OK)"
    proxies = urllib.request.getproxies()
    proxy_url = proxies.get("http") or proxies.get("https") or "不明"
    return f"VIA PROXY ({proxy_url}) ← NO_PROXY に {host} を追加が必要"


def create_llm() -> ChatOpenAI:
    c = get_llm_config()
    return ChatOpenAI(
        temperature=c.llm_temperature,
        model=c.llm_model,
        base_url=f"http://{c.llm_ip}:{c.llm_port}/v1",
        api_key=c.llm_api_key,
    )


class AgentRunner:
    def run_agent(self, agent_input) -> str:
        """AgentInputを受け取りLLMに投げてレスポンスを返す。

        プロンプトは app_settings.get_settings().agent_prompt_template を使用。
        設定画面から変更可能。
        """
        recent_history = "\n".join(
            [f"{msg.agent_name}: {msg.content}" for msg in agent_input.history]
        )

        rag_section = (
            f"参考情報 (RAG):\n{agent_input.rag_context}"
            if agent_input.rag_context
            else "参考情報 (RAG): なし"
        )

        pre_info_section = (
            f"事前情報:\n{agent_input.pre_info}"
            if agent_input.pre_info
            else "事前情報: なし"
        )

        stance_section = (
            f"【あなたの立場・ミッション】\n{agent_input.stance_prompt}"
            if agent_input.stance_prompt
            else ""
        )

        prompt_template = PromptTemplate(
            input_variables=[
                "role", "task", "name", "query",
                "pre_info_section", "stance_section", "rag_section",
                "history", "previous_summaries", "output_format",
            ],
            template=get_settings().agent_prompt_template,
        )

        formatted_prompt = prompt_template.format(
            role=agent_input.persona.role,
            task=agent_input.task,
            name=agent_input.persona.name,
            query=agent_input.query,
            pre_info_section=pre_info_section,
            stance_section=stance_section,
            rag_section=rag_section,
            history=recent_history,
            previous_summaries=agent_input.previous_summaries,
            output_format=agent_input.output_format,
        )

        response = self._invoke_llm(formatted_prompt)
        return response.content

    def _invoke_llm(self, prompt: str):
        """常に最新の設定でLLMを生成して呼び出す。"""
        c = get_llm_config()
        base_url = f"http://{c.llm_ip}:{c.llm_port}/v1"
        endpoint = f"{base_url}/chat/completions"
        proxy = _proxy_status(endpoint)

        logger.info(f"[Host→LLM] POST {endpoint}")
        logger.info(f"  model={c.llm_model}  prompt_chars={len(prompt)}")
        logger.info(f"  proxy: {proxy}")
        logger.info(
            f"  # 手動確認 (ホストから実行):\n"
            f"  curl -v --noproxy '*' -X POST {endpoint} \\\n"
            f"    -H 'Content-Type: application/json' \\\n"
            f"    -H 'Authorization: Bearer $LLM_API_KEY' \\\n"
            f"    -d '{{\"model\":\"{c.llm_model}\","
            f"\"messages\":[{{\"role\":\"user\",\"content\":\"ping\"}}]}}'"
        )

        start = time.time()
        try:
            result = create_llm().invoke(prompt)
            elapsed_ms = (time.time() - start) * 1000
            logger.info(f"[LLM→Host] OK  ({elapsed_ms:.1f}ms)")
            return result
        except Exception as e:
            elapsed_ms = (time.time() - start) * 1000
            logger.error(f"[LLM ERROR] POST {endpoint}  ({elapsed_ms:.1f}ms)")
            logger.error(f"  {type(e).__name__}: {e}")
            logger.error(f"  proxy: {proxy}")
            logger.error(
                f"  # モデル一覧で疎通確認:\n"
                f"  curl -v --noproxy '*' {base_url}/models \\\n"
                f"    -H 'Authorization: Bearer $LLM_API_KEY'"
            )
            raise

    def _run_one_theme(self, session: SessionMemory) -> str:
        """現在のテーマを実行して要約を返す。workflow/turn_runner.py に委譲。"""
        return run_one_theme(
            session=session,
            agent_executor=self.run_agent,
            summarizer=lambda s: summarize_theme(s, create_llm()),
        )

    def _summarize_current_theme(self, session: SessionMemory) -> str:
        """現在のテーマを要約して返す。workflow/summarizer.py に委譲。"""
        return summarize_theme(session, create_llm())

    # -------------------------------------------------------------------
    # 全テーマをシーケンシャルに実行するメインエントリ
    # -------------------------------------------------------------------
    def run_full_session_background(self, session_id: str, job_id: str):
        """全テーマを session.project_flow に従って処理し、最終レポートを生成する。"""
        try:
            job_statuses[job_id] = {"status": "processing"}
            session = session_manager.get_session(session_id)
            if not session:
                raise ValueError("Session not found")
            if not session.personas:
                raise ValueError("No personas available")

            run_full_session(
                session=session,
                agent_executor=self.run_agent,
                summarizer=lambda s: summarize_theme(s, create_llm()),
            )

            theme_summaries = [
                ThemeSummary(theme=s["theme"], summary=s["summary"])
                for s in session.summaries
            ]
            final_report = "\n\n".join(
                f"## {s.theme}\n{s.summary}" for s in theme_summaries
            )

            job_statuses[job_id] = {
                "status": "completed",
                "result": FullSessionResult(
                    theme_summaries=theme_summaries,
                    final_report=final_report,
                ).model_dump(),
            }

        except Exception as e:
            job_statuses[job_id] = {"status": "error", "error_msg": str(e)}

    # -------------------------------------------------------------------
    # 既存API互換 (ターン単位 / 要約単位)
    # -------------------------------------------------------------------
    def start_turn_background(self, session_id: str, job_id: str):
        try:
            job_statuses[job_id] = {"status": "processing"}
            session = session_manager.get_session(session_id)
            if not session:
                raise ValueError("Session not found")
            if session.all_themes_done:
                job_statuses[job_id] = {
                    "status": "completed",
                    "all_themes_done": True,
                    "is_theme_end": True,
                }
                return

            active = session.active_personas
            if not active:
                raise ValueError("No active personas for current theme")

            # テーマ最初のターンで特許分析を実行（patent_configが設定されている場合）
            patent_context: str | None = None
            if session.turn_count_in_theme == 0:
                try:
                    patent_context = _run_patent_analysis_for_theme(session)
                except Exception as pe:
                    logger.error(f"[Patent] テーマ開始時の特許分析に失敗: {pe}")

            persona = select_persona(active, session)
            agent_input = build_agent_input(session, persona, patent_context=patent_context)
            message = self.run_agent(agent_input)

            session.history.append(MessageHistory(
                id=_uuid.uuid4().hex,
                theme=session.current_theme,
                agent_name=persona.name,
                content=message,
                turn_order=session.turn_count_in_theme,
            ))
            session.turn_count_in_theme += 1
            is_theme_end = session.turn_count_in_theme >= session.current_turns_per_theme

            job_statuses[job_id] = {
                "status": "completed",
                "agent_name": persona.name,
                "message": message,
                "theme": session.current_theme,
                "is_theme_end": is_theme_end,
                "history_compressed": agent_input.history_compressed,
                "rag_context": agent_input.rag_context or None,
                "patent_context": patent_context,
            }

        except Exception as e:
            job_statuses[job_id] = {"status": "error", "error_msg": str(e)}

    def summarize_background(self, session_id: str, job_id: str):
        try:
            job_statuses[job_id] = {"status": "processing"}
            session = session_manager.get_session(session_id)
            if not session:
                raise ValueError("Session not found")

            should_summarize = True
            if session.current_theme_config is not None:
                should_summarize = session.current_theme_config.summarize
            summary_text = self._summarize_current_theme(session) if should_summarize else ""
            session.advance_theme(summary_text)

            job_statuses[job_id] = {
                "status": "completed",
                "summary_text": summary_text,
                "all_themes_done": session.all_themes_done,
            }

        except Exception as e:
            job_statuses[job_id] = {"status": "error", "error_msg": str(e)}


def _build_discussion_context(session: SessionMemory, pc) -> str:
    """前テーマまでの議論内容をLLM向けのテキストにまとめる。"""
    parts: List[str] = []
    for source in (pc.pre_info_sources or []):
        if source.startswith("summary:"):
            try:
                n = int(source.split(":")[1]) - 1
                if 0 <= n < len(session.summaries):
                    s = session.summaries[n]
                    parts.append(f"[テーマ{n+1}: {s['theme']}の要約]\n{s['summary']}")
            except (ValueError, IndexError):
                pass
        elif source.startswith("messages:"):
            try:
                n = int(source.split(":")[1]) - 1
                theme_n_theme = session.themes[n].theme if n < len(session.themes) else ""
                theme_msgs = [m for m in session.history if m.theme == theme_n_theme and m.agent_name not in ('Summary', '[会話圧縮]')]
                if theme_msgs:
                    msgs_text = "\n\n".join(f"{m.agent_name}: {m.content}" for m in theme_msgs)
                    parts.append(f"[テーマ{n+1}: {theme_n_theme}の発言]\n{msgs_text}")
            except (ValueError, IndexError):
                pass
    # pre_info_sources未設定でも直前テーマの要約を自動追加
    if not pc.pre_info_sources and session.summaries:
        last = session.summaries[-1]
        parts.append(f"[直前テーマ: {last['theme']}の要約]\n{last['summary']}")
    return "\n\n".join(parts)


def _get_csv_rows(session: SessionMemory, pc) -> List[dict]:
    """patent_configのcsvまたはsession.patent_rowsからCSV行データを取得する。"""
    # csv_idが指定されている場合はセッションキャッシュから取得
    if pc.csv_id and hasattr(session, 'patent_csv_cache') and pc.csv_id in session.patent_csv_cache:
        return session.patent_csv_cache[pc.csv_id]
    # フォールバック: sessionに直接渡された行データ
    return session.patent_rows


def _run_patent_analysis_for_theme(session: SessionMemory) -> str | None:
    """テーマのpatent_configに従って特許統計・分析を実行し、レポートを返す。

    フロー:
      1. stats_processorsが設定されている場合:
         a. 各プロセッサについてparam_promptがあればLLMがパラメータを生成
         b. パラメータを使って統計処理を実行（機械的）
         c. final_llm_promptが設定されていればLLMで整理
      2. system_promptが設定されている場合: 既存のLLM分析も実行
      3. 結果を結合してエージェント入力に渡す
    """
    theme_index = session.current_theme_index

    # キャッシュチェック
    if theme_index in session.patent_context_cache:
        return session.patent_context_cache[theme_index]

    cfg = session.current_theme_config
    if cfg is None or cfg.patent_config is None:
        return None

    pc = cfg.patent_config
    settings = get_settings()
    rows = _get_csv_rows(session, pc)
    if not rows:
        logger.warning("[Patent] CSV行データが空のため特許分析をスキップします")
        return None

    company_col = settings.patent_company_column
    content_col = settings.patent_content_column
    date_col = settings.patent_date_column

    # 企業フィルター適用（selected_companiesが空なら全企業）
    filter_companies = set(pc.selected_companies) if pc.selected_companies else set()
    max_companies = pc.max_companies or 20
    max_total_patents = pc.max_total_patents or 100
    patents_per_company = pc.patents_per_company or 10

    # 前テーマの議論コンテキスト（LLMパラメータ生成に使用）
    discussion_context = _build_discussion_context(session, pc)

    report_parts: List[str] = []
    llm = create_llm()

    # ─── 統計処理フロー ──────────────────────────────────
    if pc.stats_processors:
        col_settings = {
            "company_col": company_col,
            "date_col": date_col,
            "content_col": content_col,
        }

        # selected_companiesで事前フィルター（統計処理用）
        stats_rows = [r for r in rows
                      if not filter_companies or (r.get(company_col) or "").strip() in filter_companies]

        run_configs = [
            ProcessorRunConfig(
                processor_id=sp.processor_id,
                param_prompt=sp.param_prompt,
                variable_name=sp.variable_name,
                ipc_col=sp.ipc_col,
            )
            for sp in pc.stats_processors
            if sp.enabled
        ]

        stat_results = run_stats_with_configs(
            rows=stats_rows,
            configs=run_configs,
            settings=col_settings,
            llm=llm if any(c.param_prompt for c in run_configs) else None,
            discussion_context=discussion_context,
        )

        combined_md = results_to_markdown(stat_results)

        if pc.final_llm_prompt and combined_md:
            # 変数を置換してLLMで整理
            variables = results_to_variables(stat_results)
            prompt = pc.final_llm_prompt
            for var_name, var_value in variables.items():
                prompt = prompt.replace(f"{{{{{var_name}}}}}", var_value)
            prompt = prompt.replace("{{stats_all}}", combined_md)
            try:
                llm_summary = llm.invoke(prompt).content
                report_parts.append(f"## 統計分析\n\n{llm_summary}")
            except Exception as e:
                logger.warning(f"[Patent] 統計LLM整理に失敗: {e}")
                report_parts.append(combined_md)
        elif combined_md:
            report_parts.append(f"## 統計データ\n\n{combined_md}")

    # ─── 既存LLM分析フロー（後方互換） ───────────────────
    if pc.system_prompt or pc.output_format:
        from collections import defaultdict
        company_patents: dict = defaultdict(list)
        for row in rows:
            company = (row.get(company_col) or "").strip()
            content = (row.get(content_col) or "").strip()
            date = (row.get(date_col) or "").strip()
            if company and content:
                if filter_companies and company not in filter_companies:
                    continue
                company_patents[company].append(PatentItem(content=content, date=date))

        if company_patents:
            sorted_companies = sorted(company_patents.keys(), key=lambda c: len(company_patents[c]), reverse=True)
            sorted_companies = sorted_companies[:max_companies]

            patents_by_company: List[dict] = []
            total = 0
            for company in sorted_companies:
                patents = sorted(company_patents[company], key=lambda p: p.date, reverse=True)[:patents_per_company]
                if total + len(patents) > max_total_patents:
                    patents = patents[:max_total_patents - total]
                patents_by_company.append({"company": company, "patents": patents})
                total += len(patents)
                if total >= max_total_patents:
                    break

            system_prompt = pc.system_prompt or ""
            if discussion_context:
                system_prompt = discussion_context + ("\n\n" + system_prompt if system_prompt else "")

            output_format = pc.output_format or ""
            strategy = pc.strategy or "bulk"
            chunk_size = pc.chunk_size or 20
            company_label = "・".join(p["company"] for p in patents_by_company[:3])
            if len(patents_by_company) > 3:
                company_label += "..."

            try:
                if strategy == "chunked":
                    all_patents = [
                        PatentItem(content=f"[{p['company']}] {pt.content}", date=pt.date)
                        for p in patents_by_company for pt in p["patents"]
                    ]
                    req = PatentChunkedAnalyzeRequest(
                        company=company_label, patents=all_patents,
                        system_prompt=system_prompt, output_format=output_format,
                        chunk_size=chunk_size, max_prompt_tokens=settings.patent_max_prompt_tokens,
                    )
                    result = analyze_chunked(req, llm,
                                            max_prompt_tokens=settings.patent_max_prompt_tokens,
                                            chunk_analyze_prompt=settings.patent_chunk_analyze_prompt,
                                            chunk_reduce_prompt=settings.patent_chunk_reduce_prompt)
                    report_parts.append(result.report)
                else:
                    compress_mode = None
                    if strategy == "bulk_per_patent":
                        compress_mode = "per_patent"
                    elif strategy == "bulk_per_company":
                        compress_mode = "per_company"

                    all_patents: List[PatentItem] = []
                    for p in patents_by_company:
                        if compress_mode:
                            comp_req = PatentCompressRequest(
                                patents=p["patents"], mode=compress_mode, company=p["company"],
                            )
                            prompt_key = "per_patent" if compress_mode == "per_patent" else "per_company"
                            comp_prompt = (settings.patent_compress_per_patent_prompt
                                          if prompt_key == "per_patent"
                                          else settings.patent_compress_per_company_prompt)
                            comp_req = comp_req.model_copy(update={"compress_prompt": comp_prompt})
                            try:
                                comp_result = compress_patents(comp_req, llm)
                                for pt in comp_result.patents:
                                    all_patents.append(PatentItem(content=f"[{p['company']}] {pt.content}", date=pt.date))
                            except Exception:
                                for pt in p["patents"]:
                                    all_patents.append(PatentItem(content=f"[{p['company']}] {pt.content}", date=pt.date))
                        else:
                            for pt in p["patents"]:
                                all_patents.append(PatentItem(content=f"[{p['company']}] {pt.content}", date=pt.date))

                    req = PatentAnalyzeRequest(
                        company=company_label, patents=all_patents,
                        system_prompt=system_prompt, output_format=output_format,
                        max_prompt_tokens=settings.patent_max_prompt_tokens,
                    )
                    report_parts.append(analyze_company(req, llm, max_prompt_tokens=settings.patent_max_prompt_tokens))
            except Exception as e:
                logger.error(f"[Patent] LLM分析に失敗: {e}")

    if not report_parts:
        return None

    report = "\n\n---\n\n".join(report_parts)
    session.patent_context_cache[theme_index] = report
    return report


agent_runner = AgentRunner()
