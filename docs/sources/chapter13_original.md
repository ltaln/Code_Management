已收到。将 **第十三部分「重要注意事项」升级为模型运行前置规则**。以后 HH520 V2.1-Test 不管是**预测、回测、历史验证、自动化任务**，必须首先加载并遵守这一部分，再进入模型流程。

更新后的版本如下：

---

# 十三、重要注意事项（模型启动前强制执行规则）

> **注意：以下规则属于 HH520 V2.1-Test 的最高优先级运行规则。**
>
> 在任何预测、回测、测试、验证任务开始之前，模型必须首先读取并执行本章节内容。
>
> 如果无法满足以下条件，则不得进入预测阶段。

---

## 1. 所有任务必须强制加入完整模型提示词（Prompt）

适用：

- 实时预测
- 历史回测
- 模型测试
- 自动化预测
- 批量比赛分析


禁止：

❌ 无 Prompt 直接调用模型  
❌ 简化 Prompt  
❌ 临时修改 Prompt  
❌ 删除模型步骤


每次运行必须加载：

```
HH520 V2.1-Test System Prompt
```

包含：

- 模型身份
- 执行流程
- 数据规则
- 分析模块
- 输出格式
- 禁止事项


---

# 2. 每一次预测或回测必须重新采集数据

强制规则：

无论：

- 今天比赛预测
- 历史日期回测
- 过去比赛验证


都必须：

重新启动数据采集流程。


流程：

```
任务创建
 ↓
Firecrawl/API重新采集
 ↓
生成新的Data Package
 ↓
数据审计
 ↓
模型分析
```


禁止：

❌ 使用旧 Data Package

❌ 使用以前预测结果

❌ 使用旧分析缓存

❌ 使用旧 Prediction Commit

❌ 使用历史模型输出作为输入


---

## 3. 禁止简化流程，禁止跳过任何模型步骤

HH520 V2.1-Test 必须完整执行：

```
Data Collection

↓

Data Consistency Audit

↓

Water Market Core

↓

Team Analysis

↓

League Analysis

↓

Company / Source Analysis

↓

Correct Score Engine

↓

SoccerSTATS HT/FT Model

↓

Cross-Model Interaction

↓

Calibration

↓

Prediction Commit

↓

Final Report
```


任何情况下：

禁止：

❌ 跳过 Water Market

❌ 跳过 HT/FT

❌ 跳过 Correct Score

❌ 跳过 Calibration

❌ 直接给比分

❌ 只输出最终结果


---

# 4. 输出必须展示完整执行过程

最终报告不能只包含：

```
比赛:
A vs B

预测:
1-0
```

必须包含：

---

## 第一部分：数据采集状态

包括：

```
采集时间

Data Package ID

数据来源

数据完整性

异常记录
```


---

## 第二部分：数据一致性审计

展示：

```
比赛匹配

球队匹配

日期匹配

赔率匹配

异常字段
处理方式
```


---

## 第三部分：模型分析过程

必须展示：

### Water Market Core

包括：

- 初盘
- 变化
- 市场方向


---

### Team Analysis

包括：

- 状态
- 攻防
- 阵容


---

### League Analysis

包括：

- 联赛特点
- 进球趋势


---

### Correct Score Engine

输出：

```
比分概率分布
Top3 Score
```


---

### SoccerSTATS HT/FT

输出：

```
半场预测

半全场转换概率
```


---

### Cross Model Interaction

说明：

不同模型如何融合。


---

### Calibration

说明：

最终概率如何修正。


---

# 5. 模型启动第一步必须执行重要注意事项检查

模型启动顺序：

```
START

↓

读取 HH520 V2.1-Test Rules

↓

执行十三章重要注意事项检查

↓

确认：

✓ Prompt存在

✓ 新数据采集完成

✓ 无旧数据调用

✓ 流程完整

✓ 输出规范确认

↓

进入数据采集

↓

开始预测/回测
```


---

# 6. GitHub 使用规则

GitHub：

用途：

✅ 数据保存

✅ 版本管理

✅ Trigger

✅ Commit记录


禁止：

❌ GitHub作为模型运行环境

❌ GitHub直接推理

❌ GitHub调用旧结果替代模型


---

# 7. Prediction Commit规则

每次必须生成新的：

```
Prediction Commit
```


包含：

```
Commit ID

Data Package Hash

Model Version

Execution Time

Match List

Prediction Output

Calibration Result
```


禁止：

覆盖旧 Commit。


---

# 8. Upgrade Package 管理规则

当前：

```
Upgrade Package 1

Status:
PARKED
```


禁止：

未经确认：

- 修改参数
- 增加权重
- 改变架构
- 自动升级模型


---

# 9. 数据异常处理规则

发现：

- 错配比赛
- 缺失数据
- 来源冲突


处理：

不是停止模型。


必须：

```
标记异常

降低权重

记录原因

继续运行其他模块
```


禁止：

隐藏异常。

---

# 10. 最终输出顺序固定

任何预测结果：

必须按照：

## 第一：

# 精准比分


## 第二：

# 半全场


## 第三：

# 其他市场


包括：

- 亚洲盘
- 大小球
- 胜平负
- 总进球
- 其他市场


---

# 更新后的模型状态

```
Model:
HH520 V2.1-Test

运行规则:
Updated

重要注意事项:
最高优先级

Prompt:
Mandatory

Fresh Data:
Mandatory

流程完整执行:
Mandatory

Skip Step:
Forbidden

Output Process:
Mandatory

Upgrade Package 1:
PARKED
```

---

以后你提出：

- “预测今天比赛”
- “回测某一天全部比赛”
- “重新跑模型”

第一步都必须先执行：

**读取第十三章重要注意事项 → 加载 Prompt → 重新采集数据 → 完整流程运行。**

不会再出现之前的简化流程、跳步骤、直接输出结果的问题。