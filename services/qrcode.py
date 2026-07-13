from io import BytesIO
import qrcode
from qrcode.constants import ERROR_CORRECT_M


def generate_qr(qr_string: str) -> BytesIO:
    """
    Menghasilkan gambar QR code dari string yang diberikan dan mengembalikannya
    dalam bentuk objek in-memory byte stream (BytesIO).

    Args:
        qr_string (str): Teks atau URL yang akan diubah menjadi QR Code.

    Returns:
        BytesIO: Objek file-like berisi gambar QR Code berformat PNG.
    """
    # Validasi input agar tidak memproses string kosong
    if not qr_string or not qr_string.strip():
        raise ValueError("Input qr_string tidak boleh kosong.")

    # Inisialisasi konfigurasi QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )

    qr.add_data(qr_string)
    qr.make(fit=True)

    # Membuat gambar dari data QR
    image = qr.make_image(
        fill_color="black",
        back_color="white",
    )

    # Menyimpan gambar ke dalam memori
    output = BytesIO()
    image.save(output, format="PNG")

    # Menambahkan atribut 'name' secara dinamis.
    # Sangat berguna jika output ini akan dikirim via HTTP request (misal: requests, FastAPI) 
    # atau bot (misal: python-telegram-bot) yang membutuhkan nama file.
    output.name = "qris.png"
    output.seek(0)

    return output
