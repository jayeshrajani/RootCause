"""Fetch DINOv2 ViT-S/14 weights and write a local `facebook/dinov2-small` model directory.

Usage (from apps/api, with the retrieval extra installed):

    python scripts/fetch_dinov2.py --data-dir C:/rootcause-data

Hugging Face's file CDN is blocked on some corporate networks, so the weights come from Meta's
official host (checksum pinned) and are converted to the Hugging Face layout. Only the two small
config files are read from huggingface.co. Re-running reuses verified files.
"""

import argparse
import json
import re
import ssl
import sys
from pathlib import Path

import httpx
import truststore

from app.core.config import Settings
from app.services.retrieval.dataset_registry import RemoteFile, atomic_write_bytes
from app.services.retrieval.downloads import download_file
from app.services.retrieval.embeddings import DINOV2_SMALL, default_model_dir, sha256_file

META_CHECKPOINT = RemoteFile(
    url="https://dl.fbaipublicfiles.com/dinov2/dinov2_vits14/dinov2_vits14_pretrain.pth",
    filename="dinov2_vits14_pretrain.pth",
    size=88_283_115,
    sha256="b938bf1bc15cd2ec0feacfe3a1bb553fe8ea9ca46a7e1d8d00217f29aef60cd9",
)
HF_CONFIG_FILES = ("config.json", "preprocessor_config.json")

_TOP_LEVEL = {
    "cls_token": "embeddings.cls_token",
    "mask_token": "embeddings.mask_token",
    "pos_embed": "embeddings.position_embeddings",
    "patch_embed.proj.weight": "embeddings.patch_embeddings.projection.weight",
    "patch_embed.proj.bias": "embeddings.patch_embeddings.projection.bias",
    "norm.weight": "layernorm.weight",
    "norm.bias": "layernorm.bias",
}
_BLOCK = {
    "norm1": "norm1",
    "norm2": "norm2",
    "attn.proj": "attention.output.dense",
    "ls1.gamma": "layer_scale1.lambda1",
    "ls2.gamma": "layer_scale2.lambda1",
    "mlp.fc1": "mlp.fc1",
    "mlp.fc2": "mlp.fc2",
}


def convert(meta_state: dict[str, object], dim: int) -> dict[str, object]:
    """Rename Meta's ViT keys to Hugging Face Dinov2Model keys; split fused qkv projections."""
    converted: dict[str, object] = {}
    for key, tensor in meta_state.items():
        if key in _TOP_LEVEL:
            converted[_TOP_LEVEL[key]] = tensor
            continue
        match = re.fullmatch(r"blocks\.(\d+)\.(.+)", key)
        if not match:
            raise ValueError(f"unexpected checkpoint key {key!r}")
        prefix, rest = f"encoder.layer.{match.group(1)}.", match.group(2)
        if rest in ("attn.qkv.weight", "attn.qkv.bias"):
            kind = rest.rsplit(".", 1)[1]
            for part, name in enumerate(("query", "key", "value")):
                converted[f"{prefix}attention.attention.{name}.{kind}"] = tensor[  # type: ignore[index]
                    part * dim : (part + 1) * dim
                ]
            continue
        for source, target in _BLOCK.items():
            if rest == source or rest.startswith(source + "."):
                converted[prefix + target + rest[len(source) :]] = tensor
                break
        else:
            raise ValueError(f"unexpected checkpoint key {key!r}")
    return converted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--data-dir", type=Path, help="Defaults to ROOTCAUSE_DATA_DIR.")
    parser.add_argument("--model-dir", type=Path, help="Defaults to DATA_DIR/models/<model>/<rev>.")
    args = parser.parse_args(argv)
    data_dir: Path | None = args.data_dir or Settings().data_dir
    if data_dir is None:
        print("Set --data-dir or ROOTCAUSE_DATA_DIR.", file=sys.stderr)
        return 2
    spec = DINOV2_SMALL
    model_dir: Path = args.model_dir or default_model_dir(data_dir.resolve(), spec)
    weights = model_dir / "model.safetensors"
    if weights.is_file() and sha256_file(weights) == spec.weights_sha256:
        print(f"Model already present and verified: {model_dir}")
        return 0

    import safetensors.torch
    import torch
    from transformers import Dinov2Model

    client = httpx.Client(
        verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
        timeout=httpx.Timeout(120, connect=20),
        follow_redirects=True,
    )
    with client:
        checkpoint = download_file(
            client, META_CHECKPOINT, data_dir / "models" / "meta" / META_CHECKPOINT.filename
        )
        for name in HF_CONFIG_FILES:
            url = f"https://huggingface.co/{spec.model_id}/resolve/{spec.model_revision}/{name}"
            response = client.get(url)
            response.raise_for_status()
            json.loads(response.content)
            atomic_write_bytes(model_dir / name, response.content)

    meta_state = torch.load(checkpoint, map_location="cpu", weights_only=True)
    state = {k: v.contiguous() for k, v in convert(meta_state, spec.dimension).items()}  # type: ignore[attr-defined]

    # Hub-format key names; transformers maps them onto its current module names when loading.
    tmp = weights.with_name(weights.name + ".tmp")
    safetensors.torch.save_file(state, str(tmp), metadata={"format": "pt"})
    tmp.replace(weights)
    _model, info = Dinov2Model.from_pretrained(
        str(model_dir), local_files_only=True, output_loading_info=True
    )
    problems = {k: v for k, v in info.items() if k != "error_msgs" and v} | (
        {"error_msgs": info["error_msgs"]} if info.get("error_msgs") else {}
    )
    if problems:
        weights.unlink()
        print(f"Converted weights did not load cleanly: {problems}", file=sys.stderr)
        return 1
    digest = sha256_file(weights)
    print(f"Wrote {weights} ({weights.stat().st_size} bytes, sha256 {digest})")
    if digest != spec.weights_sha256:
        print("WARNING: converted weights differ from the pinned checksum.", file=sys.stderr)
        return 1
    print("Converted weights are byte-identical to the published facebook/dinov2-small file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
