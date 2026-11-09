"""Barcode symbologies, looked up by name: `get("qr").to_png("hello")`."""

from qrbar.symbologies.base import DEFAULT_SCALE, Symbology, get, names, register
from qrbar.symbologies.linear import Code128Symbology, Ean13Symbology, UpcaSymbology
from qrbar.symbologies.matrix import AztecSymbology, DataMatrixSymbology, Pdf417Symbology
from qrbar.symbologies.qr import QrSymbology

__all__ = ["DEFAULT_SCALE", "Symbology", "get", "names", "register"]

register(QrSymbology())

register(Code128Symbology())

register(Ean13Symbology())

register(UpcaSymbology())

register(DataMatrixSymbology())

register(Pdf417Symbology())

register(AztecSymbology())
