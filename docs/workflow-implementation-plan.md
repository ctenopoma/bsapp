# ワークフロー実装計画

## 完了: Phase 1（基礎的な連携 / 実装難易度：低）

- [x] `strategies/base.py` — ThemeStrategy 基底クラス
- [x] `strategies/sequential.py` — シーケンシャル（現行ロジック移植）
- [x] `strategies/parallel.py` — 並列独立（ブレスト）
- [x] `strategies/round_robin_debate.py` — ラウンドロビン（順番ディベート）
- [x] `turn_runner.py` をストラテジーディスパッチャーに書き換え
- [x] `models.py` に `theme_strategy`, `strategy_config` 追加
- [x] フロントエンド型定義 + SetupScreen にストラテジー選択UI追加

---

## Phase 1.5: ペルソナ発言順の制御（実装難易度：低）

テーマごとに「どのペルソナをどの順番で当てるか」をユーザーが明示的に指定できるようにする。
全ストラテジー共通の基盤機能。

### バックエンド

- [ ] `ThemeConfig` に `persona_order: List[str]` 追加（ペルソナIDの順序リスト、空=従来通り）
  - 空の場合: 既存の `persona_selector.py` のストラテジー（round_robin等）で選択
  - 指定ありの場合: リスト順に固定で発言させる
- [ ] `persona_selector.py` に `custom_order` ストラテジー追加
  - `ThemeConfig.persona_order` に従い、リスト順にペルソナを返す
  - ループ時はリスト先頭に戻る
  - リストに含まれないペルソナはスキップ
- [ ] `persona_order` が設定されている場合、ストラテジー内で自動的に `custom_order` を使用するよう `strategies/base.py` に共通ロジック追加
- [ ] 各ストラテジー（sequential, parallel, round_robin_debate）が `persona_order` を尊重するよう調整

### フロントエンド

- [ ] `ThemeConfig` 型に `persona_order?: string[]` 追加
- [ ] SetupScreen のテーマカード内に「発言順」の並び替えUI追加
  - ドラッグ&ドロップ or 上下矢印ボタンでペルソナの順番を変更
  - 「カスタム順」チェックボックスで有効/無効を切り替え
  - 無効時は従来通りストラテジー任せ
- [ ] `ThemeEntry` に `personaOrder: string[]` 追加、`dbToUi`/`uiToDb` を更新
- [ ] プリセット保存時に `persona_order` も含める

### 考慮事項

- Phase 2以降のストラテジー（階層型、敵対的等）では「役割ベースの指定」（マネージャー=何番目、批判役=何番目）がこの発言順と連携する
  - `persona_order[0]` = マネージャー/生成役/司会者、のように暗黙マッピング可能
  - 明示的な `manager_index` 等の設定と `persona_order` の両方がある場合は `strategy_config` が優先

---

## Phase 2: 品質向上と制御（実装難易度：中）

LLMに「評価」「判定」させるロジックを組み込む。出力の質が劇的に上がるフェーズ。

### 2-1. 階層型（計画・実行・反省）

- [ ] `strategies/hierarchical.py` 新規作成
- [ ] マネージャー/ワーカーのロール分離
  - マネージャーが「計画」を出す → ワーカーが「実行」→ マネージャーが「評価」
  - 評価はJSON構造化出力（`{"pass": true/false, "feedback": "..."}`）
  - 不合格なら修正ループ（最大N回）
- [ ] `strategy_config` に追加する設定項目:
  - `manager_index`: マネージャー役（デフォルト: `persona_order[0]` or 0）
  - `max_revision_loops`: 最大修正ループ数（デフォルト: 3）
  - `pass_condition`: 合格判定プロンプト（省略可）
- [ ] `prompt_builder.py` に評価用テンプレート `EVALUATION_PROMPT_TEMPLATE` 追加
- [ ] フロントエンド `THEME_STRATEGIES` に定義追加 + 設定UI

### 2-2. 敵対的・レッドチーム（生成・批判）

- [ ] `strategies/adversarial.py` 新規作成
- [ ] 「生成役」と「批判役」に分かれ、ダメ出しと修正を往復
  - 生成役が提案 → 批判役がダメ出し → 生成役が修正 → ...
  - 最大往復数に達したら終了
- [ ] `strategy_config` に追加する設定項目:
  - `generator_index`: 生成役（デフォルト: `persona_order[0]` or 0）
  - `critic_index`: 批判役（デフォルト: `persona_order[1]` or 1）
  - `max_rounds`: 最大往復数（デフォルト: 3）
  - `critic_perspective`: 批判の観点（省略可、例: "セキュリティ面から"）
- [ ] `prompt_builder.py` に批判用テンプレート `CRITIC_PROMPT_TEMPLATE` 追加
- [ ] フロントエンド `THEME_STRATEGIES` に定義追加 + 設定UI

### 2-3. 陪審員・裁判官（Judge & Jury）

- [ ] `strategies/judge_jury.py` 新規作成
- [ ] ディベーター間で議論 → 裁判官が最終判定
  - ディベーターは全履歴を共有して議論（ラウンドロビン形式）
  - 議論終了後、裁判官が全履歴を読み最終決定を下す
- [ ] `strategy_config` に追加する設定項目:
  - `judge_index`: 裁判官役（デフォルト: `persona_order` の最後 or 最後のペルソナ）
  - `debate_turns`: ディベートのターン数（デフォルト: 6）
  - `evaluation_criteria`: 評価基準（省略可）
- [ ] フロントエンド `THEME_STRATEGIES` に定義追加 + 設定UI

### Phase 2 共通タスク

- [ ] `strategies/__init__.py` の `STRATEGY_MAP` にPhase 2 の全ストラテジーを登録
- [ ] フロントエンドの `THEME_STRATEGIES` 配列に全ストラテジー定義を追加
- [ ] 動作確認（各ストラテジーでセッション実行）

---

## Phase 3: 高度な自律性と動的処理（実装難易度：高）

JSON構造化出力によるプログラム的分岐制御。LLMの出力をパースして次の処理を決定する。

### 3-1. 動的ルーティング（司会者主導）

- [ ] `strategies/dynamic_routing.py` 新規作成
- [ ] 司会者（ルーター）が直前の文脈から「次に誰が発言すべきか」をJSON指名
  - ルーターのLLM出力: `{"next_speaker": "ペルソナ名", "reason": "..."}`
  - パースして指名されたペルソナを次の発言者にする
  - 終了条件を満たしたらループ終了
- [ ] `strategy_config`:
  - `router_index`: 司会者（デフォルト: `persona_order[0]` or 0）
  - `max_turns`: 最大ターン数
  - `end_condition`: 終了条件プロンプト
- [ ] JSON出力強制のためのシステムプロンプト追加
- [ ] JSONパースエラー時のフォールバック処理

### 3-2. 分割統治（Map-Reduce）

- [ ] `strategies/map_reduce.py` 新規作成
- [ ] プランナーがタスク分割 → ワーカーが並行処理 → サマライザーが統合
  - プランナーLLM出力: `{"subtasks": ["タスク1", "タスク2", ...]}`
  - 各ワーカーがサブタスクを独立して実行
  - サマライザーが全結果を統合
- [ ] `strategy_config`:
  - `planner_index`: プランナー役
  - `summarizer_index`: サマライザー役
  - `max_subtasks`: 最大分割数
- [ ] 並行処理の制御（現時点では同期でも可、将来的にasyncio対応）

### 3-3. 動的エージェント生成

- [ ] `strategies/dynamic_generation.py` 新規作成
- [ ] メタエージェントが課題に合わせ、最適なペルソナをその場で生成
  - メタエージェントLLM出力: `{"personas": [{"name": "...", "role": "...", "pre_info": "..."}, ...]}`
  - 一時ペルソナを SessionMemory に追加して議論実行
- [ ] `strategy_config`:
  - `meta_agent_index`: メタエージェント役
  - `max_generated`: 同時生成する最大数
  - `generation_guideline`: 編成指針
- [ ] 生成されたペルソナの一時管理（セッション終了時に破棄）

### Phase 3 共通タスク

- [ ] JSON構造化出力のユーティリティ関数作成（パース + バリデーション + フォールバック）
- [ ] `strategies/__init__.py` への登録
- [ ] フロントエンド `THEME_STRATEGIES` への追加

---

## Phase 4: マクロワークフロー（テーマ間の進行制御）

現在の `agent_runner.py` の「テーマを順番に実行」を `orchestrator.py` に抽出し、テーマ間の進行ルールを差し替え可能にする。

### 4-1. アーキテクチャ変更

- [ ] `workflow/flows/base.py` — `ProjectFlow` 基底クラス作成
- [ ] `workflow/flows/waterfall.py` — ウォーターフォール型（現行ロジック移植）
- [ ] `workflow/orchestrator.py` — マクロフロー・ディスパッチャー
- [ ] `agent_runner.py` の `run_full_session_background` をオーケストレーターに委譲
- [ ] `SessionStartRequest` に `project_flow` フィールド追加

### 4-2. ステージゲート型

- [ ] `workflow/flows/stage_gate.py` 新規作成
- [ ] テーマ間にゲートキーパー判定を挟む
  - テーマ完了 → ゲートキーパーが品質チェック → 不合格なら差し戻し
- [ ] 設定: ゲートキーパー役、通過条件、最大差し戻し回数

### 4-3. アジャイル/スプリント型

- [ ] `workflow/flows/agile_sprint.py` 新規作成
- [ ] テーマ群を1スプリントとし、複数回ループ
- [ ] 設定: スプリント回数、完成判定者

### 4-4. 条件分岐/ツリー型

- [ ] `workflow/flows/conditional.py` 新規作成
- [ ] テーマの結論によって次のテーマが分岐
- [ ] 設定: ルーター役、分岐条件ルール

### Phase 4 共通タスク

- [ ] フロントエンドにマクロフロー選択UI追加（SetupScreen のセッション設定セクション）
- [ ] プリセットデータに `project_flow` 設定を保存
