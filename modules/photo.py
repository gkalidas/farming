import httpx
from config import OLLAMA_URL, VISION_MODEL
from .base import BaseModule, ModuleContext


class PhotoModule(BaseModule):
    name = "photo"

    async def analyze(self, image_b64: str, crop: str) -> ModuleContext:
        prompt = (
            f"You are an expert agricultural scientist specializing in {crop} cultivation.\n"
            f"Analyze this photo of a {crop} plant or fruit carefully.\n\n"
            "Identify:\n"
            "1. The specific disease, condition, or health status visible\n"
            "2. Severity: healthy / mild / moderate / severe\n"
            "3. Affected parts: leaf / fruit / stem / root / whole plant\n"
            "4. Confidence: high / medium / low\n"
            "5. Key visual symptoms you can see\n\n"
            "Be specific and concise. If the plant looks healthy, say so clearly."
        )
        payload = {
            "model": VISION_MODEL,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
            r.raise_for_status()
            diagnosis = r.json()["response"].strip()

        return ModuleContext(
            module_name=self.name,
            available=True,
            summary=f"Visual diagnosis: {diagnosis}",
            detail={"raw_diagnosis": diagnosis},
        )

    # satisfies the abstract contract; real entry point is analyze()
    async def get_context(self, crop: str, location: str, date: str) -> ModuleContext:
        return ModuleContext(
            module_name=self.name,
            available=False,
            summary="No image provided",
        )
