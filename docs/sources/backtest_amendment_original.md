已修改。这个调整是合理的，因为**回测场景和预测场景的数据逻辑不同**。之前“所有回测必须重新采集”过于严格，会导致已经存在有效预测记录时重复消耗采集资源。

现在修改为：

# 十三、重要注意事项（更新版）

## 2. 数据使用规则（预测 / 回测分别处理）

### A. 实时预测规则

任何实时预测：

必须：

```
重新采集最新数据

↓

生成新的 Data Package

↓

执行完整 HH520 V2.1-Test 流程
```

禁止：

❌ 使用旧预测数据  
❌ 使用旧分析结果  
❌ 使用旧 Prediction Commit


---

# B. 回测规则（修改）

回测分两种情况：

---

## 情况1：已有对应日期预测数据

如果系统中已经存在：

```
Prediction Data Package

+

Prediction Result

+

Prediction Commit
```

则：

直接调用已有预测数据。


流程：

```
输入回测日期

↓

检查 Prediction Archive

↓

找到对应 Prediction Commit

↓

读取预测结果

↓

获取真实比赛结果

↓

执行数据对比

↓

生成 Evaluation Report
```


不需要：

重新采集。


---

## 情况2：没有对应日期预测数据

如果不存在：

```
Prediction Data Package
```

或者：

```
Prediction Commit
```

则：

必须重新执行预测流程。


流程：

```
指定回测日期

↓

重新采集当时可用数据

↓

生成新的 Data Package

↓

执行 HH520 V2.1-Test完整预测流程

↓

生成 Prediction Commit

↓

获取真实结果

↓

执行数据对比

↓

生成 Evaluation Report
```


---

# C. 回测禁止事项

无论哪种情况：

禁止：

❌ 使用赛后数据重新预测

❌ 使用最终比分影响预测过程

❌ 修改历史预测结果

❌ 根据结果调整模型参数


---

# D. 回测数据优先级

回测调用顺序：

```
第一优先级：

已有 Prediction Commit


↓

第二优先级：

已有历史 Prediction Data Package


↓

第三优先级：

重新采集历史数据重新预测
```


---

# E. 回测目标

回测不是重新预测一次。

核心目标：

验证：

```
当时模型看到的信息

↓

产生的预测

↓

与真实结果比较
```


因此：

已有预测：

直接验证。


没有预测：

先模拟当时预测环境。


---

# 更新后的模型规则

现在：

## 预测

```
Fresh Data Mandatory
```

必须新采集。


---

## 回测

```
Prediction Archive First
```

优先调用历史预测。


没有：

```
Fresh Historical Data Required
```

重新采集。


---

这样修改后更符合长期运行系统设计：

优点：

1. **节约 Firecrawl/API 资源**
2. **保证历史预测可复盘**
3. **避免重复生成不同版本的同一天预测**
4. **支持真正的模型准确率统计**
5. **保留完整 Prediction Commit 链路**

同时不改变：

```
HH520 V2.1-Test核心模型
Upgrade Package 1:
PARKED
```

只是优化数据生命周期管理规则。