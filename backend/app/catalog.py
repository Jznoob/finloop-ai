from __future__ import annotations

from app.models import Product, Segment

SEGMENTS: dict[str, Segment] = {
    "steady-planner": Segment(
        id="steady-planner",
        name="稳健规划者",
        description="关注回撤、流动性与资金规划，对剧烈波动较敏感。",
        risk_level=2,
        preferred_channel="app",
        concerns=["回撤控制", "资金流动性", "风险解释"],
    ),
    "growth-explorer": Segment(
        id="growth-explorer",
        name="成长探索者",
        description="有较长持有周期，愿意承担波动，但需要清晰的仓位纪律。",
        risk_level=4,
        preferred_channel="wechat",
        concerns=["长期成长", "入场节奏", "组合纪律"],
    ),
    "pro-allocator": Segment(
        id="pro-allocator",
        name="专业配置者",
        description="理解复杂产品与情景分析，重视数据依据和组合相关性。",
        risk_level=5,
        preferred_channel="email",
        concerns=["多资产相关性", "情景压力测试", "策略容量"],
    ),
}


PRODUCTS: dict[str, Product] = {
    "DEMO-FI-01": Product(
        id="DEMO-FI-01",
        name="安盈短债增强",
        risk_level=2,
        category="固收+",
        horizon="6—18 个月",
        highlights=["波动控制", "较好流动性", "信用分散"],
        risks=["利率风险", "信用风险", "净值波动"],
    ),
    "DEMO-EQ-02": Product(
        id="DEMO-EQ-02",
        name="星河指数增强",
        risk_level=4,
        category="权益量化",
        horizon="3 年以上",
        highlights=["宽基暴露", "量化增强", "风格约束"],
        risks=["权益市场波动", "模型失效", "跟踪偏离"],
    ),
    "DEMO-MA-03": Product(
        id="DEMO-MA-03",
        name="远航全球配置",
        risk_level=3,
        category="多资产",
        horizon="2 年以上",
        highlights=["跨资产分散", "动态再平衡", "全球配置"],
        risks=["市场风险", "汇率风险", "流动性风险"],
    ),
}


def get_segment(segment_id: str) -> Segment:
    return SEGMENTS.get(segment_id, SEGMENTS["steady-planner"])
