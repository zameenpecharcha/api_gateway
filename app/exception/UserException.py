from graphql import GraphQLError

class REException(Exception):
    """Custom Exception for API errors"""

    def __init__(self, code: str, message: str, reason: str):
        super().__init__(message)
        self.code = code
        self.message = message
        self.reason = reason

    def to_graphql_error(self):
        """Convert to a GraphQL-friendly error response."""
        return GraphQLError(f"{self.code}: {self.message} - {self.reason}")
