"""
workflow/patent/prompt_builder.py
===================================
特許調査用のデフォルトプロンプトと出力フォーマット。

★ ここを書き換えることで分析指示・レポート構成を変更できます ★

変数プレースホルダー:
  PATENT_ANALYZE_TEMPLATE      : {system_prompt}, {company}, {patents}, {output_format}
  PATENT_SUMMARY_TEMPLATE      : {system_prompt}, {reports}
  COMPRESS_PER_PATENT_TEMPLATE : {patent}
  COMPRESS_PER_COMPANY_TEMPLATE: {company}, {patents}
  CHUNK_ANALYZE_TEMPLATE       : {system_prompt}, {company}, {chunk_no}, {total_chunks}, {patents}, {count}
  CHUNK_REDUCE_TEMPLATE        : {system_prompt}, {company}, {chunk_count}, {intermediate_reports}, {output_format}
"""

# -------------------------------------------------------------------
# 企業別分析プロンプト
# -------------------------------------------------------------------
PATENT_ANALYZE_TEMPLATE = """\
{system_prompt}

## 分析対象企業
{company}

## 特許リスト ({count}件)
{patents}

{output_format}
"""

# -------------------------------------------------------------------
# 総括プロンプト
# -------------------------------------------------------------------
PATENT_SUMMARY_TEMPLATE = """\
{system_prompt}

## 各企業の特許分析レポート

{reports}

上記のすべての企業レポートをもとに、業界全体の技術動向と各社の競争優位性を総括してください。
"""

# -------------------------------------------------------------------
# 圧縮プロンプト
# -------------------------------------------------------------------
COMPRESS_PER_PATENT_TEMPLATE = """\
以下の特許を1〜2文に要約してください。技術的な核心のみを簡潔に述べてください。

{patent}

要約:"""

COMPRESS_PER_COMPANY_TEMPLATE = """\
以下は{company}の特許リストです。これらを統合して、主要な技術領域と研究方向性を3〜5文にまとめてください。

{patents}

まとめ:"""

# -------------------------------------------------------------------
# チャンク分割Reduce プロンプト
# -------------------------------------------------------------------
CHUNK_ANALYZE_TEMPLATE = """\
{system_prompt}

## 分析対象企業
{company}

## 特許リスト（チャンク {chunk_no}/{total_chunks}、{count}件）
{patents}

以下の点に注目して、このチャンクの特許群を分析してください。
最終的に複数チャンクの結果をまとめるため、このチャンク内の技術的特徴・キーワード・傾向を具体的に記述してください。
"""

CHUNK_REDUCE_TEMPLATE = """\
{system_prompt}

## 分析対象企業
{company}

## チャンクごとの中間分析結果（全{chunk_count}チャンク）

{intermediate_reports}

上記の全チャンクの分析結果を統合し、最終レポートを作成してください。

{output_format}
"""

# -------------------------------------------------------------------
# デフォルト値 (クライアントで未設定の場合にフォールバック)
# -------------------------------------------------------------------
DEFAULT_ANALYZE_SYSTEM_PROMPT = """\
あなたは特許分析の専門家です。
与えられた企業の特許リストを分析し、技術的な強みや研究開発の方向性を把握してください。"""

DEFAULT_ANALYZE_OUTPUT_FORMAT = """\
以下のフォーマットでレポートを作成してください:

## {company} 分析レポート

### 主な技術領域
（特許から読み取れる主要な技術分野を3点以内で列挙）

### 研究開発の方向性
（技術トレンドや注力分野を2〜3文で述べる）

### 注目特許
（特に注目すべき特許のタイトルと理由を1〜2件挙げる）"""

DEFAULT_SUMMARY_SYSTEM_PROMPT = """\
あなたは特許分析の専門家です。
複数企業の特許分析レポートを総括し、業界全体の技術動向と各社の競争優位性を分析してください。"""
