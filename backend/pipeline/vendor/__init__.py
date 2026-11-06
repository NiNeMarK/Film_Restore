"""อาร์คิเทกเจอร์โมเดลที่คัดลอกโค้ดต้นทางมา (vendored)

เหตุผลที่ vendor: ทั้ง CodeFormer และ SCUNet ไม่มีใน PyPI และตัวต้นทางผูกกับ
basicsr / timm / thop ซึ่งเป็น dependency หนักและชนกับ torch รุ่นใหม่
เราเก็บเฉพาะไฟล์อาร์คิเทกเจอร์ (โครงข่าย) แล้วโหลด weights เองผ่าน ModelManager

ไฟล์และต้นทาง:
- ``vqgan_arch.py``      — sczhou/CodeFormer, ``basicsr/archs/vqgan_arch.py`` (Apache-2.0)
- ``codeformer_arch.py`` — sczhou/CodeFormer, ``basicsr/archs/codeformer_arch.py`` (Apache-2.0)
- ``scunet_arch.py``     — cszn/SCUNet, ``models/network_scunet.py`` (Apache-2.0)

สิ่งที่แก้จากต้นฉบับ (นอกจาก import ที่ชี้มาที่ ``_compat``):
- ตัด ``from thop import profile`` ของ SCUNet ออก (ใช้แค่ใน ``__main__`` นับ FLOPs)
- เปลี่ยน ``timm.models.layers`` เป็น ``_compat.trunc_normal_`` / ``_compat.DropPath``
- เปลี่ยน ``basicsr.utils`` เป็น ``_compat.get_root_logger`` / ``_compat.ARCH_REGISTRY``

ตัวโมเดลเอง (โครงข่าย/การคำนวณ) ไม่ได้แก้ไข เพื่อให้โหลด weights ต้นทางได้ตรง ๆ
"""

from __future__ import annotations

__all__ = ["CodeFormer", "SCUNet"]


def __getattr__(name: str):
    """import แบบ lazy: โหลดโมเดลไหนใช้จริงเฉพาะตอนที่ถูกเรียก

    ทำให้ SCUNet ไม่ต้องพึ่ง einops ตอนใช้แค่ CodeFormer (และกลับกัน)
    """
    if name == "CodeFormer":
        from .codeformer_arch import CodeFormer

        return CodeFormer
    if name == "SCUNet":
        from .scunet_arch import SCUNet

        return SCUNet
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
