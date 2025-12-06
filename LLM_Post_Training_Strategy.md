# 应用经济学大模型 Post-Training 语料策略思考

当前语料收集平台已经解决了数据的 **“获取”** 和 **“基础清洗”** 问题。为了将这些数据高效用于 LLM 的 Post-Training（SFT Supervised Fine-Tuning 或 DPO Direct Preference Optimization），我们需要从 **模型训练视角** 进行更深层次的规划。

以下是建议的后续建设方向：

## 1. 数据格式标准化 (Data Formatting)

原始的“问题-选项-答案-解析”结构需要转化为模型可理解的指令微调格式。

-   **指令模版设计 (Prompt Engineering)**
    -   **System Prompt**: 定义模型角色（如“你是一位资深的应用经济学教授...”）。
    -   **Instruction Construct**:
        -   *选择题*: `User: 请回答以下应用经济学问题：{stem} 选项：{options}。 Assistant: 正确答案是 {answer}。解析：{analysis}`
        -   *思维链 (CoT) 强化*: 对于简答/论述题，应强制模型先输出思考过程。`Assistant: 思考：{analysis_steps}... 因此，结论是...`
-   **兼容主流格式**:
    -   导出适配 **Alpaca**, **ShareGPT**, **ChatML** 等主流训练框架（如 LLaMA-Factory）所需的 JSONL 格式。

## 2. 高阶质量控制 (Advanced Quality Control)

基础的空值/乱码检测不足以满足训练需求，需要“语义级”清洗。

-   **语义去重 (Semantic De-duplication)**:
    -   **现状**: 不同试卷可能包含同一道真题，仅文字微小差异。
    -   **方案**: 使用 Embedding 模型（如 BGE / M3E）计算题目相似度，设定阈值（如 >0.95）进行去重，避免模型死记硬背。
-   **解析质量评分 (Reasoning Quality)**:
    -   **问题**: 部分“解析”可能只是“详见教材 P30”或“略”，这种数据对训练有害（毒数据）。
    -   **方案**:
        -   **Heuristic**: 过滤掉长度 < 10 字符的解析。
        -   **Model-based**: 使用强模型（如 GPT-4 / DeepSeek-V3）对“解析”的丰富度打分（0-5分），仅保留高分数据。
-   **答案一致性**:
    -   确保“解析”中的推导过程确实能得出“正确答案”，防止幻觉训练。

## 3. 数据配比与课程学习 (Data Mixture & Curriculum)

单纯喂入所有数据可能导致模型偏科。

-   **难度分级**:
    -   利用元数据（本科/研究生/职业资格）或模型评估，给题目打标 Difficulty Level。
    -   **Curriculum Learning**: 训练时先喂简单概念题，再喂复杂案例分析题。
-   **任务平衡**:
    -   控制 *选择题* vs *开放性问题* 的比例。
        -   过多选择题可能导致模型倾向于输出 "A/B/C/D" 而变哑。
        -   策略：将部分选择题改写为填空题或判断理由题进行训练。
-   **领域覆盖**:
    -   监控 宏观/微观/金融/计量 等子领域的分布，通过重采样（Up-sampling）平衡弱势学科。

## 4. 偏好对齐数据构建 (DPO/RLHF Preparation)

为了进一步提升模型性能，可以构建 *偏好数据集*。

-   **构造负样本 (Negative Sampling)**:
    -   利用错误选项作为负例。
    -   `Chosen Response`: 正确解析。
    -   `Rejected Response`: 利用错误选项生成的似是而非的解析（Hard Negative）。
-   **协同标注升级**:
    -   利用前面提到的“协同标注”功能，不仅是修错，更是让专家对模型生成的多个回答进行 Ranking（排序），直接用于训练 Reward Model。

## 5. 增强检索能力 (RAG Readiness)

应用经济学模型不仅需要内化知识，更需要引用依据。

-   **知识库挂载**:
    -   将习题中的“相关知识点”字段结构化，建立知识图谱或向量索引。
    -   训练模型学会 **"检索-阅读-回答"** 模式，而不仅仅是封闭问答。

---

## 建议的实施路线图

1.  **Phase 1 (Format)**: 开发 `Data Export` 模块，支持一键导出 `alpaca_data.json`。
2.  **Phase 2 (Filter)**: 引入 Embedding 模型，实现库内语义去重。
3.  **Phase 3 (Review)**: 利用大模型API（Teacher Model）对现有语料的解析质量进行自动打分与清洗。
4.  **Phase 4 (Alignment)**: 构建 DPO 数据集，针对易错题进行强化。
