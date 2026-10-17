"""Correct speech transcripts and classify vehicle commands with Ollama."""

from ollama import Client

from .command_parsing import CommandInterpretation
from .misc import config_file, prompts


class TextToCommandWorkflow:
    """Run correction and command classification in one constrained request."""

    def __init__(
        self,
        model_name,
        base_url="http://localhost:11434",
        enable_stt_correction=True,
        client=None,
    ):
        self.model_name = model_name
        self.enable_stt_correction = enable_stt_correction
        self.last_corrected_text = ""

        if client is not None:
            self.client = client
            return

        client_options = {
            "host": base_url,
            "timeout": 30.0,
        }
        token = config_file.llm_param.get("openweb_ui_token", "").strip()
        if token:
            client_options["headers"] = {
                "Authorization": f"Bearer {token}",
            }

        self.client = Client(**client_options)

    def text_to_command(self, text):
        """Return one validated action and retain the corrected transcript."""
        if self.enable_stt_correction:
            correction_policy = (
                "Apply only minimal, highly likely speech-recognition "
                "corrections. If no correction is clearly justified, return "
                "the original transcript unchanged."
            )
        else:
            correction_policy = (
                "Do not correct or rewrite the transcript. Copy the original "
                "transcript exactly into corrected_text."
            )

        prompt = prompts.command_interpretation_prompt.format(
            car_actions_l=prompts.car_actions_l,
            correction_policy=correction_policy,
            command_txt=text,
        )
        response = self.client.chat(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            format=CommandInterpretation.model_json_schema(),
            think=False,
            stream=False,
            keep_alive="30m",
            options={
                "temperature": 0,
                "num_ctx": 2048,
                "num_predict": 96,
            },
        )

        result = CommandInterpretation.model_validate_json(
            response.message.content
        )
        corrected_text = result.corrected_text.strip()
        if not self.enable_stt_correction or not corrected_text:
            corrected_text = text

        self.last_corrected_text = corrected_text
        return result.action.value
