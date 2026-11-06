"""ตัวช่วยแทนส่วนที่อาร์คิเทกเจอร์ที่ vendor มาอ้างถึงจากไลบรารีภายนอก

- `basicsr.utils.get_root_logger` / `basicsr.utils.registry.ARCH_REGISTRY`
  ใช้โดย vqgan_arch.py และ codeformer_arch.py ของ CodeFormer — เราไม่ต้องการ
  ติดตั้ง basicsr (มันลาก dependency หนักและชนกับ torch รุ่นใหม่) จึงทำชิมเล็ก ๆ
  ที่ทำงานเทียบเท่าในกรณีของเรา (registry เป็น no-op, logger เป็น logging ธรรมดา)
- `timm.models.layers.trunc_normal_` / `DropPath` ใช้โดย SCUNet — เราใช้
  `torch.nn.init.trunc_normal_` ที่มีมาใน torch อยู่แล้ว และเขียน DropPath เอง
  (โค้ดเดียวกับที่ timm ใช้) เพื่อไม่ต้องติดตั้ง timm ทั้งแพ็กเกจ
"""

from __future__ import annotations

import logging

import torch
from torch import nn

LOGGER_NAME = "film_restore.vendor"


class _ArchRegistry:
    """registry ปลอม: ทำหน้าที่แค่รับ decorator แล้วคืนคลาสเดิม"""

    def register(self, obj=None):
        def _wrap(cls):
            return cls

        if obj is None:
            return _wrap
        return obj


ARCH_REGISTRY = _ArchRegistry()


def get_root_logger(*_args, **_kwargs) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


# ---------- แทน timm.models.layers ----------
trunc_normal_ = torch.nn.init.trunc_normal_


class DropPath(nn.Module):
    """Stochastic depth ต่อ sample (เหมือน timm.models.layers.DropPath)

    SCUNet สร้าง DropPath เฉพาะตอน ``drop_path > 0`` ซึ่งใช้เฉพาะตอน train
    แต่ต้องมีคลาสนี้ให้ import ได้
    """

    def __init__(self, drop_prob: float = 0.0):
        super().__init__()
        self.drop_prob = float(drop_prob)

    def forward(self, x):
        if self.drop_prob == 0.0 or not self.training:
            return x
        keep_prob = 1.0 - self.drop_prob
        shape = (x.shape[0],) + (1,) * (x.ndim - 1)
        random_tensor = keep_prob + torch.rand(shape, dtype=x.dtype, device=x.device)
        random_tensor.floor_()
        return x.div(keep_prob) * random_tensor

    def extra_repr(self) -> str:
        return f"drop_prob={self.drop_prob}"
