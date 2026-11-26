"""Build the model and Square backend from settings."""

from strands.models import Model

from agent_service.settings import Settings
from agent_service.square.backend import BookingBackend
from agent_service.square.client import SquareGateway
from agent_service.square.fake import FakeSquareGateway


def build_backend(settings: Settings) -> BookingBackend:
    if settings.square_mode == "fake":
        return FakeSquareGateway(settings.tz)
    return SquareGateway.from_settings(settings)


def build_model(settings: Settings) -> Model:
    if settings.model_provider == "anthropic":
        from strands.models.anthropic import AnthropicModel

        if not settings.anthropic_api_key:
            raise ValueError("MODEL_PROVIDER=anthropic needs ANTHROPIC_API_KEY")
        return AnthropicModel(
            client_args={"api_key": settings.anthropic_api_key},
            model_id=settings.anthropic_model_id,
            max_tokens=1024,
        )

    import boto3
    from botocore.exceptions import ProfileNotFound
    from strands.models import BedrockModel

    try:
        session = boto3.Session(
            profile_name=settings.aws_profile or None, region_name=settings.aws_region
        )
    except ProfileNotFound as error:
        raise ValueError(
            f"AWS profile '{settings.aws_profile}' not found. Run `aws configure sso` "
            "or fix AWS_PROFILE."
        ) from error
    config = {"model_id": settings.bedrock_model_id} if settings.bedrock_model_id else {}
    return BedrockModel(boto_session=session, **config)
