下面是对 **HH520 V2.1-Test 足球预测模型** 的完整梳理版本。  
我按照目前实际执行流程整理，不做简化。后续所有预测、回测、自动化流程必须以此作为标准 SOP。

# HH520 V2.1-Test Model Specification

## 一、模型定位

### 模型名称
**HH520 V2.1-Test**

### 核心目标
不是单纯预测胜负，而是建立：

> 数据采集 → 数据审计 → 多模型融合 → 市场校准 → 概率分布 → 比分预测 → 半全场预测 → 市场选择

完整预测系统。

---

# 二、总体架构

```
                 Firecrawl / API / Web Data
                         |
                         ↓
              Data Collection Layer
                         |
                         ↓
              Data Consistency Audit
                         |
                         ↓
        --------------------------------
        |              |               |
        ↓              ↓               ↓
   Water Market   Team Analysis   External Data
        |              |               |
        --------------------------------
                         |
                         ↓
               Feature Engineering
                         |
                         ↓
        --------------------------------
        |              |               |
        ↓              ↓               ↓
 Correct Score   HT/FT Model   Market Model
        |              |               |
        --------------------------------
                         |
                         ↓
              Cross-Model Interaction
                         |
                         ↓
                  Calibration Layer
                         |
                         ↓
              Final Prediction Commit
                         |
                         ↓
             Output Report
```

---

# 三、数据来源架构

## 1. Firecrawl 数据层

用途：

只负责：

- 页面采集
- 数据保存
- 触发流程

禁止：

❌ 作为预测环境  
❌ 直接运行模型  
❌ 修改模型逻辑


GitHub：

```
ltaln/firecrawl-gpt-predictor
```

作用：

- 数据资产管理
- issue trigger
- commit 管理


---

# 四、采集标准流程

## Step 1

Issue Trigger

例如：

```
Issue #12
Date: 2026-09-03
Task:
Collect all matches
```

生成：

```
Raw Data Package
```

必须包含：

```
match_list
team_info
odds
lineup
history
stats
market_data
```

---

# 五、数据一致性审计（硬性步骤）

任何预测前必须执行。

## Audit 1：比赛身份校验

检查：

```
Home Team
Away Team
League
Match ID
Date
```

必须100%一致。


错误案例：

```
比赛:
皇家社会 vs 塞尔塔

赔率页面:
巴列卡诺 vs 阿拉维斯

=> 数据污染
```

处理：

```
该数据字段权重 = 0
```

不能删除。

---

## Audit 2：时间一致性

检查：

```
比赛日期
采集时间
赔率更新时间
阵容更新时间
```

禁止：

使用未来信息。

---

## Audit 3：重复数据检测

禁止：

```
旧Prediction Commit
旧Data Package
旧Analysis Result
```

混入。


---

# 六、核心分析模块

---

# Module 1
# Water Market Core

核心：

盘口资金模型。


输入：

```
Asian Handicap
European Odds
Movement
Volume
Closing Line
```

分析：

## 1. 初盘

例如：

```
主队 -0.5
```

## 2. 变化

例如：

```
-0.5 → -0.25
```

判断：

市场真实方向。


---

输出：

```
Market Direction Score

0-100
```

例如：

```
Home pressure:
72

Away resistance:
61
```

---

# Module 2
# Team Analysis

包含：

## 最近状态

```
Last 5
Last 10
Home/Away
```

指标：

- 进球
- 失球
- xG
- xGA
- 射门
- 控球
- 防守质量


---

## 阵容因素

分析：

- 首发
- 伤停
- 轮换
- 核心球员


权重：

```
重要比赛:
提高

弱联赛:
降低
```

---

# Module 3
# League Analysis

分析：

联赛特点：

例如：

```
瑞典超:
开放

法甲:
防守结构更强

巴西杯:
杯赛不确定性高
```


指标：

- 平均进球
- 主胜率
- 大小球率
- 半场趋势


---

# Module 4
# Company / Source Analysis

来源可信度模型。


例如：

不同网站：

```
HH520
SoccerSTATS
Opta
API
News
```

建立：

Source Reliability Score


示例：

```
赔率:
90%

历史统计:
85%

新闻:
70%
```

---

# Module 5
# Correct Score Engine

核心比分预测。


输入：

```
Attack Strength
Defense Strength
xG
Market
Poisson
Historical
Simulation
```

输出：

Top Score Distribution


格式：

```
1-0 18%

1-1 16%

2-1 14%
```


---

# Module 6
# SoccerSTATS HT/FT Model


拆分：

## Stage A

半场预测。


输入：

```
HT Goal Trend
First Half xG
Early Pressure
```

输出：

```
HT Result
```

例如：

```
平
```


---

## Stage B

半场 → 全场转换


例如：

```
HT 平

↓

FT 主胜概率
```

考虑：

- 换人
- 体能
- 后程进球


---

# 七、Cross-Model Interaction

这是 V2.1 的核心。


不是简单平均。


例如：

Correct Score：

```
1-1
```

Market：

```
客队优势
```

HT：

```
平
```


系统重新计算：

```
Final Probability
```

避免：

单模型偏差。

---

# 八、Calibration 校准层

目标：

降低模型过度自信。


例如：

模型：

```
主胜 75%
```

Calibration 后：

```
主胜 62%
```

考虑：

- 联赛波动
- 数据质量
- 市场异常


---

# 九、硬性指标

## 数据质量

必须：

|指标|要求|
|-|-|
|比赛身份匹配|100%|
|时间一致|100%|
|重复检测|通过|
|来源记录|必须|

---

## 模型执行

必须执行：

✅ Data Audit

✅ Water Market Core

✅ Correct Score

✅ SoccerSTATS HT/FT

✅ Team Analysis

✅ League Analysis

✅ Company Source Analysis

✅ Cross Model Interaction

✅ Calibration


禁止跳过。


---

# 十、输出格式标准


最终报告顺序：

## 第一部分

# 精准比分

格式：

```
比赛

Top1:
1-1

Top2:
1-0

Top3:
2-1


Confidence:
68%
```


---

## 第二部分

# 半全场


格式：

```
HT/FT:

平/主胜

概率:
```

---

## 第三部分

其他市场


顺序：

1. 亚洲盘

2. 大小球

3. 胜平负

4. 总进球

5. 角球/其他


---

# 十一、Prediction Commit 标准


每次预测必须生成：

```
Prediction Commit ID

包含：

- Data Hash
- Model Version
- Timestamp
- Match List
- Prediction Result
- Calibration Result
```

禁止：

覆盖旧 Commit。

---

# 十二、Prompt 固定模板

以后调用模型必须带：

```
你现在运行 HH520 V2.1-Test。

严格执行完整流程：

1. 使用当前唯一数据包。
2. 禁止调用历史Prediction。
3. 禁止复用旧分析。
4. 首先执行Data Consistency Audit。
5. 数据错误字段降低权重，不允许隐藏。
6. 完整执行：

Water Market Core
Correct Score Engine
SoccerSTATS HT/FT
Team Analysis
League Analysis
Company Source Analysis
Cross-Model Interaction
Calibration

7. 输出必须：

比分第一
半全场第二
其他市场随后。

8. Upgrade Package 1保持PARKED。
9. 不修改模型参数。
```

---

# 十三、重要注意事项

## 1.
数据错误 ≠ 预测失败

例如：

10017错配：

正确处理：

```
该字段废弃
其他模型继续运行
降低Confidence
```

---

## 2.
不能为了输出而强行预测

如果：

数据质量：

<70%

必须：

降低置信度。


---

## 3.
不能自动升级模型

任何：

Upgrade Package

必须人工批准。


当前：

```
Upgrade Package 1:
PARKED
```

---

## 4.
GitHub定位

GitHub：

✅ 数据仓库  
✅ 版本管理  
✅ Trigger

不是：

❌ 模型服务器  
❌ 推理环境


---

# 十四、当前模型状态

```
Model:
HH520 V2.1-Test

Status:
ACTIVE

Upgrade Package 1:
PARKED

Prediction Engine:
GPT执行

GitHub:
Storage + Trigger only

Data Policy:
Single Fresh Snapshot Only

Old Prediction:
禁止复用
```

---

以上就是当前版本完整模型 SOP。  
后续所有 **回测、每日预测、自动化预测** 都应以这个版本执行。