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

## 完了: Phase 2（品質向上と制御 / 実装難易度：中）

LLMに「評価」「判定」させるロジックを組み込む。出力の質が劇的に上がるフェーズ。

### 2-1. 階層型（計画・実行・反省）

- [x] `strategies/hierarchical.py` 新規作成
- [x] マネージャー/ワーカーのロール分離
  - マネージャーが「計画」を出す → ワーカーが「実行」→ マネージャーが「評価」
  - 評価はJSON構造化出力（`{"pass": true/false, "feedback": "..."}`）
  - 不合格なら修正ループ（最大N回）
- [x] `strategy_config` に設定項目追加:
  - `manager_index`, `max_revision_loops`, `pass_condition`
- [x] `prompt_builder.py` に評価用テンプレート `EVALUATION_PROMPT_TEMPLATE` 追加
- [x] フロントエンド `THEME_STRATEGIES` に定義追加 + 設定UI

### 2-2. 敵対的・レッドチーム（生成・批判）

- [x] `strategies/adversarial.py` 新規作成
- [x] 「生成役」と「批判役」に分かれ、ダメ出しと修正を往復
- [x] `strategy_config` に設定項目追加:
  - `generator_index`, `critic_index`, `max_rounds`, `critic_perspective`
- [x] `prompt_builder.py` に批判用テンプレート `CRITIC_PROMPT_TEMPLATE` 追加
- [x] フロントエンド `THEME_STRATEGIES` に定義追加 + 設定UI

### 2-3. 陪審員・裁判官（Judge & Jury）

- [x] `strategies/judge_jury.py` 新規作成
- [x] ディベーター間で議論 → 裁判官が最終判定
- [x] `strategy_config` に設定項目追加:
  - `judge_index`, `debate_turns`, `evaluation_criteria`
- [x] フロントエンド `THEME_STRATEGIES` に定義追加 + 設定UI

### Phase 2 共通タスク

- [x] `strategies/__init__.py` の `STRATEGY_MAP` にPhase 2 の全ストラテジーを登録
- [x] フロントエンドの `THEME_STRATEGIES` 配列に全ストラテジー定義を追加

---

## 完了: Phase 3（高度な自律性と動的処理 / 実装難易度：高）

JSON構造化出力によるプログラム的分岐制御。LLMの出力をパースして次の処理を決定する。

### 3-1. 動的ルーティング（司会者主導）

- [x] `strategies/dynamic_routing.py` 新規作成
- [x] 司会者（ルーター）が直前の文脈から「次に誰が発言すべきか」をJSON指名
  - ルーターのLLM出力: `{"next_speaker_index": N, "reason": "..."}`
- [x] `strategy_config`: `router_index`, `max_turns`, `end_condition`

### 3-2. 分割統治（Map-Reduce）

- [x] `strategies/map_reduce.py` 新規作成
- [x] プランナーがタスク分割 → ワーカーが処理 → サマライザーが統合
  - プランナーLLM出力: `{"subtasks": ["タスク1", "タスク2", ...]}`
- [x] `strategy_config`: `planner_index`, `summarizer_index`, `max_subtasks`

### 3-3. 動的エージェント生成

- [x] `strategies/dynamic_generation.py` 新規作成
- [x] メタエージェントが課題に合わせ、最適なペルソナをその場で生成
  - メタエージェントLLM出力: `{"personas": [{"name": "...", "role": "...", "pre_info": "..."}, ...]}`
- [x] `strategy_config`: `meta_agent_index`, `max_generated`, `generation_guideline`

### Phase 3 共通タスク

- [x] JSON構造化出力ユーティリティ `json_utils.py` 作成（パース + フォールバック）
- [x] `strategies/__init__.py` への登録
- [x] フロントエンド `THEME_STRATEGIES` への追加

---

## 完了: Phase 4（マクロワークフロー / テーマ間の進行制御）

`agent_runner.py` の「テーマを順番に実行」を `orchestrator.py` に抽出し、テーマ間の進行ルールを差し替え可能にした。

### 4-1. アーキテクチャ変更

- [x] `workflow/flows/base.py` — `ProjectFlow` 基底クラス + `FlowContext` データクラス作成
- [x] `workflow/flows/waterfall.py` — ウォーターフォール型（現行ロジック移植）
- [x] `workflow/orchestrator.py` — マクロフロー・ディスパッチャー
- [x] `agent_runner.py` の `run_full_session_background` をオーケストレーターに委譲
- [x] `SessionStartRequest` に `project_flow`, `flow_config` フィールド追加

### 4-2. ステージゲート型

- [x] `workflow/flows/stage_gate.py` 新規作成
- [x] テーマ完了 → ゲートキーパーが品質チェック → 不合格なら差し戻し
- [x] 設定: `gatekeeper_index`, `pass_condition`, `max_revisions`

### 4-3. アジャイル/スプリント型

- [x] `workflow/flows/agile_sprint.py` 新規作成
- [x] テーマ群を1スプリントとし、完成判定者が評価して複数回ループ
- [x] 設定: `sprint_count`, `completion_judge_index`, `completion_criteria`

### 4-4. 条件分岐/ツリー型

- [x] `workflow/flows/conditional.py` 新規作成
- [x] テーマの結論によってルーターが次のテーマを動的に選択
- [x] 設定: `router_index`, `routing_rules`, `max_total_themes`

### 4-5. V字型（実行＆逆順レビュー）

- [x] `workflow/flows/v_shape.py` 新規作成
- [x] 全テーマを前半で実行し、後半は逆順でレビュアーが品質フィードバック
- [x] 設定: `reviewer_index`, `review_focus`

### 4-6. ゲーム理論/対立型（陣営間ディベート）

- [x] `workflow/flows/game_theory.py` 新規作成
- [x] 提案陣営と批判陣営が複数ラウンド対立議論し、合意形成者が最終案を導く
- [x] 設定: `split_index`, `rounds`, `agreement_judge_index`, `agreement_criteria`

### 4-7. ブラックボード型（共有黒板）

- [x] `workflow/flows/blackboard.py` 新規作成
- [x] コーディネーターが共有履歴（黒板）を読み、次の担当エージェント＋テーマを動的指名
- [x] 設定: `coordinator_index`, `goal_condition`, `max_total_turns`

### 4-8. トーナメント/進化型（並列コンペ）

- [x] `workflow/flows/tournament.py` 新規作成
- [x] 同一プロジェクトを複数レーンで独立実行し、審査員が最良を選出
- [x] 設定: `num_lanes`, `judge_index`, `evaluation_criteria`

### Phase 4 共通タスク

- [x] フロントエンドにマクロフロー選択UI追加（SetupScreen のセッション設定セクション）
- [x] プリセットデータに `project_flow`, `flow_config` 設定を保存
- [x] 4つの追加プロンプトテンプレートを `prompt_builder.py` に追加
- [x] `flows/__init__.py` の `FLOW_MAP` に全8フローを登録
