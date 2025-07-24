import imageio.v2 as imageio
import cv2
from processing.liver_cc_simple import LiverCCSimple
from medical_image_processing.utils.viz import overlay_mask

# carica una slice singola (DICOM o PNG convertita)
img = imageio.imread(
    "data/liver/abdomen-lesion-dataset-phantomx/phantomx_abdomen_lesion_dataset/D53-03/40/6_120_40_BODY-SHARP_AICE_170641.498/IM-0856-0095.dcm"
)  # HU già in int16

proc = LiverCCSimple(thr=110, median_k=9, side="left")
res = proc.run(img)
ov = overlay_mask(img, res["mask"])
cv2.imshow("overlay", ov)
cv2.waitKey(0)
