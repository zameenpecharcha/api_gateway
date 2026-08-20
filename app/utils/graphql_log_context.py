from strawberry.extensions import SchemaExtension

from app.utils.request_context import set_correlation_id, set_user_id


class BindLogContextExtension(SchemaExtension):
    """Re-bind UserID / CorrelationID on the thread that executes GraphQL."""

    def on_operation(self):
        self._bind()
        yield

    def _bind(self) -> None:
        context = getattr(self.execution_context, "context", None) or {}
        if not isinstance(context, dict):
            return
        correlation_id = context.get("correlation_id")
        user_id = context.get("user_id")
        if correlation_id:
            set_correlation_id(str(correlation_id))
        if user_id:
            set_user_id(str(user_id))
