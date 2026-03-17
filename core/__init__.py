# Core 层 - 业务逻辑（意图路由、技能模块、数据串联）

from .linking import build_batch_view, match_by_sample_id
from .dispatcher import (
    Dispatcher,
    Intent,
    Handler,
    HandlerResult,
    get_dispatcher,
    register_handler,
)
from .handlers import (
    WeighTicketHandler,
    QuerySummaryHandler,
    register_handlers,
)

__all__ = [
    # linking
    "match_by_sample_id",
    "build_batch_view",
    # dispatcher
    "Dispatcher",
    "Intent",
    "Handler",
    "HandlerResult",
    "get_dispatcher",
    "register_handler",
    "WeighTicketHandler",
    "QuerySummaryHandler",
    "register_handlers",
]
