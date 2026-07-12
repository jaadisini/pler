from io import BytesIO

import qrcode
from qrcode.constants import ERROR_CORRECT_M


def generate_qr(
    qr_string: str,
):

    qr = qrcode.QRCode(
        version=1,
        error_correction=ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )

    qr.add_data(qr_string)
    qr.make(fit=True)

    image = qr.make_image(
        fill_color="black",
        back_color="white",
    )

    output = BytesIO()

    image.save(
        output,
        format="PNG",
    )

    output.name = "qris.png"
    output.seek(0)

    return output
