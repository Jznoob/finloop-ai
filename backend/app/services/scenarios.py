from app.models import RunRequest


def classify_scenario(request: RunRequest) -> str:
    """Explicit product-demo rules, not model-inferred customer facts."""
    text = f"{request.objective} {request.market_signal}"
    if any(term in text for term in ("沉默", "激活", "疲劳", "打开率下降")):
        return "reengagement"
    if any(term in text for term in ("多资产", "股债", "相关性", "海外")):
        return "multiasset"
    if any(term in text for term in ("波动", "回撤", "震荡")):
        return "volatility"
    return "education"


SCENARIOS = {
    "reengagement": {
        "title": "低负担阅读邀请",
        "intent": "先核对内容兴趣与渠道偏好，不把沉默当作购买意愿",
        "action": "自主选择想了解的主题、接收渠道或暂停接收，无需做出购买决定。",
        "clarity": "一段时间没有阅读，并不代表你需要更多消息。先选一个真正关心的问题即可。",
        "evidence": "沉默可能来自暂无需求、渠道不匹配或触达疲劳，不能据此推断购买意愿。",
        "scenario": "如果暂时没有需求，可以暂停接收；如果只想了解风险，可以选择短篇教育内容。",
    },
    "multiasset": {
        "title": "多资产风险观察清单",
        "intent": "解释资产相关性、再平衡与极端情景，避免把分散等同于无风险",
        "action": "先检查各类资产占比、相关性变化和流动性需求，再阅读组合压力情景。",
        "clarity": "理解多资产组合，可以分三步：看风险来源、看资产相关性，再看再平衡条件。",
        "evidence": "不同资产的相关性会变化，历史上的分散效果不能直接推演到未来。",
        "scenario": "若股债同时承压或汇率大幅变化，分散配置仍可能回撤，需要检查极端情景。",
    },
    "volatility": {
        "title": "波动应对清单",
        "intent": "先解释波动，再给出与承受能力匹配的行动框架",
        "action": "阅读 3 分钟情景说明，完成风险承受能力复核后再决定是否进一步了解。",
        "clarity": "市场波动变大时，先把问题拆清楚，比追逐短期方向更重要。",
        "evidence": "近期波动值得关注，但单一信号不足以推导确定结论。",
        "scenario": "如果波动延续、回落或横盘，不同情景需要不同的仓位纪律。",
    },
    "education": {
        "title": "投资教育阅读清单",
        "intent": "提供中性、可验证的配置教育，不推断客户当前购买需求",
        "action": "先了解风险等级与持有期限，结合自身需求选择教育主题。",
        "clarity": "先确认资金使用期限、流动性需求和风险承受能力，再理解产品结构。",
        "evidence": "阅读产品资料时，应同时查看适用客群、主要风险和信息来源。",
        "scenario": "如果资金提前使用或市场条件发生变化，原有配置可能需要重新评估。",
    },
}
