
import modal
from fastapi import HTTPException, Response
from pydantic import BaseModel

# Constants
MODEL_NAME_GEN = "black-forest-labs/FLUX.1-schnell"
MODEL_NAME_REMIX = "black-forest-labs/FLUX.1-Kontext-dev"
REMIX_GGUF_REPO = "unsloth/FLUX.1-Kontext-dev-GGUF"
REMIX_GGUF_FILENAME = "flux1-kontext-dev-Q4_K_S.gguf" # Using Q4_K_S (~6.8GB) for balance

# Define volumes for caching
cache_volume = modal.Volume.from_name("hf-cache", create_if_missing=True)
inductor_cache_volume = modal.Volume.from_name("inductor-cache", create_if_missing=True)

image = (
    modal.Image.from_registry("nvidia/cuda:12.4.0-devel-ubuntu22.04", add_python="3.11")
    .pip_install(
        "torch==2.5.0",
        "diffusers",
        "transformers",
        "accelerate",
        "sentencepiece",
        "huggingface_hub",
        "hf_transfer",
        "fastapi",
        "pydantic",
        "requests",
        "Pillow",
        "numpy<2",
        "protobuf"
    )
    .env({
        "HF_HUB_ENABLE_HF_TRANSFER": "1",
        "HF_HOME": "/cache",
        "TORCHINDUCTOR_CACHE_DIR": "/root/.inductor-cache",
        "TORCHINDUCTOR_FX_GRAPH_CACHE": "1",
        "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
    })
)

app = modal.App("flux-dev-service")

class GenerateRequest(BaseModel):
    prompt: str
    width: int = 1024
    height: int = 1024
    num_inference_steps: int = 4
    guidance_scale: float = 3.5

class RemixRequest(BaseModel):
    image_url: str
    prompt: str
    strength: float = 0.8 # Not used by Kontext but kept for API compat
    num_inference_steps: int = 8 # Kontext usually needs more steps
    guidance_scale: float = 2.5 # Lower guidance scale often better for edit models

def optimize_pipeline(pipe):
    """Optimize pipeline for memory efficiency and speed."""
    import torch

    # Fuse QKV projections for better performance
    if hasattr(pipe, "transformer"):
        pipe.transformer.fuse_qkv_projections()
        # Only apply channels_last to VAE (which uses Conv2d). 
        # Transformer is 3D/Sequence based, so channels_last is less relevant/risky for memory.
    
    if hasattr(pipe, "vae"):
        pipe.vae.fuse_qkv_projections()
        pipe.vae.to(memory_format=torch.channels_last)
        # Tiling handles large images by splitting them into tiles, preventing OOM.
        pipe.vae.enable_tiling()
    
    return pipe

@app.cls(
    image=image,
    gpu="L40S",
    scaledown_window=15,
    timeout=3600,
    secrets=[modal.Secret.from_name("my-custom-secret")],
    volumes={
        "/cache": cache_volume,
        "/root/.inductor-cache": inductor_cache_volume,
    },
    enable_memory_snapshot=True,
)
class FluxGen:
    @modal.enter(snap=True)
    def enter(self):
        import gc
        import torch
        
        # Fix for "No CUDA GPUs are available" during snapshot restore
        # Some libraries initialize CUDA state on import. 
        # Re-importing torch here ensures correct state detection.
        
        from diffusers import FluxPipeline

        # Load Schnell model for Generation (optimized for speed)
        print("Loading FLUX.1-schnell model (Generation)...")
        
        # CPU Memory Snapshot strategy:
        # 1. Load model to CPU first (snapshot happens here)
        # 2. Move to GPU in a non-snapshotted step OR handle it gracefully if GPU snap is off.
        # HOWEVER, since we have enable_memory_snapshot=True but NOT enable_gpu_snapshot=True (default),
        # CUDA devices are hidden during this phase.
        #
        # To fix "RuntimeError: No CUDA GPUs are available", we must:
        # A) Use enable_gpu_snapshot=True (but A100s were flaky with it)
        # B) Load to CPU here, then move to GPU in a separate @enter(snap=False) method.
        
        self.pipe = FluxPipeline.from_pretrained(
            MODEL_NAME_GEN,
            torch_dtype=torch.bfloat16
        ) # Load to CPU initially
        
        self.pipe = optimize_pipeline(self.pipe)
        
        print("Generation model loaded (CPU). Snapshotting now...")

    @modal.enter(snap=False)
    def load_gpu(self):
        import torch
        import gc
        
        print("Moving Generation model to GPU...")
        self.pipe.to("cuda")
        
        print("Warming up generation model...")
        self.pipe(
            "warmup", 
            height=256, 
            width=256, 
            num_inference_steps=1, 
            output_type="pil"
        )
        torch.cuda.synchronize()
        torch.cuda.empty_cache()
        gc.collect()
        print("Generation model ready on GPU.")

    @modal.fastapi_endpoint(method="POST", docs=True)
    def generate(self, item: GenerateRequest):
        from io import BytesIO
        
        print(f"Generating: '{item.prompt}' ({item.width}x{item.height})")
        
        image = self.pipe(
            item.prompt,
            height=item.height,
            width=item.width,
            num_inference_steps=item.num_inference_steps,
            guidance_scale=item.guidance_scale,
            output_type="pil",
        ).images[0]

        byte_stream = BytesIO()
        image.save(byte_stream, format="PNG")
        return Response(content=byte_stream.getvalue(), media_type="image/png")

@app.cls(
    image=image,
    gpu="L40S",
    scaledown_window=15,
    timeout=3600,
    secrets=[modal.Secret.from_name("my-custom-secret")],
    volumes={
        "/cache": cache_volume,
        "/root/.inductor-cache": inductor_cache_volume,
    },
    enable_memory_snapshot=True,
)
class FluxRemix:
    @modal.enter(snap=True)
    def enter(self):
        import gc
        import torch
        from diffusers import FluxKontextPipeline

        # Load Kontext model for Remix (optimized for edit)
        print("Loading FLUX.1-Kontext-dev model (Remix)...")
        # Load to CPU initially for snapshot safety
        self.pipe = FluxKontextPipeline.from_pretrained(
            MODEL_NAME_REMIX,
            torch_dtype=torch.bfloat16
        )
        
        print("Remix model loaded (CPU). Snapshotting now...")

    @modal.enter(snap=False)
    def load_gpu(self):
        import torch
        import gc
        from PIL import Image

        print("Moving Remix model to GPU...")
        self.pipe.to("cuda")
        
        print("Warming up remix model...")
        # Warmup with dummy image
        dummy_image = Image.new("RGB", (256, 256), color="white")
        
        self.pipe(
            image=dummy_image,
            prompt="warmup", 
            num_inference_steps=1, 
            output_type="pil"
        )

        torch.cuda.synchronize()
        torch.cuda.empty_cache()
        gc.collect()
        print("Remix model ready on GPU.")

    @modal.fastapi_endpoint(method="POST", docs=True)
    def remix(self, item: RemixRequest):
        from io import BytesIO

        from diffusers.utils import load_image

        print(f"Remixing: {item.image_url} with '{item.prompt}'")

        try:
            init_image = load_image(item.image_url)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to fetch image: {str(e)}")

        # Flux Kontext specific usage
        image = self.pipe(
            image=init_image,
            prompt=item.prompt,
            guidance_scale=item.guidance_scale,
            num_inference_steps=item.num_inference_steps,
            output_type="pil",
        ).images[0]

        byte_stream = BytesIO()
        image.save(byte_stream, format="PNG")
        return Response(content=byte_stream.getvalue(), media_type="image/png")

