import os
import sys
import glob
import numpy as np
import cv2
import importlib
from pathlib import Path
import pydicom


PROCESSORS = {
    "ThresholdCCL": "processing.threshold_ccl.ThresholdCCL",
    "OtsuBorder": "processing.otsu_border.OtsuBorder",
    "EdgeMorph": "processing.edge_morph.EdgeMorph",
    "LungMask": "processing.lung_mask.LungMask",
    "LiverParenchyma": "processing.liver_parenchyma.LiverParenchyma",
    "LiverCCSimple": "processing.liver_cc_simple.LiverCCSimple",
}

def print_menu(processor=None, mode=None):
    print("\n=== RSNA Pipeline Test Menu ===")
    print("1. Scegli algoritmo" + (f"   [Scelto: {processor}]" if processor else ""))
    print("2. Scegli modalità (slice/folder)" + (f"   [Scelta: {mode}]" if mode else ""))
    print("3. Esegui test")
    print("4. Esci")


def choose_processor():
    print("\nAlgoritmi disponibili:")
    for i, name in enumerate(PROCESSORS.keys(), 1):
        print(f"  {i}. {name}")
    idx = input("Scegli algoritmo [numero]: ")
    try:
        idx = int(idx)
        key = list(PROCESSORS.keys())[idx-1]
        return key
    except Exception:
        print("Scelta non valida.")
        return choose_processor()


def choose_mode():
    print("\nModalità disponibili:")
    print("  1. Slice singola (immagine)")
    print("  2. Folder completa")
    idx = input("Scegli modalità [numero]: ")
    if idx == "1":
        return "slice"
    elif idx == "2":
        return "folder"
    else:
        print("Scelta non valida.")
        return choose_mode()


def get_image_path():
    path = input("Percorso immagine: ")
    path = os.path.expanduser(path)
    if not os.path.isabs(path):
        path = os.path.abspath(path)
    if not os.path.isfile(path):
        print("File non trovato.")
        return get_image_path()
    return path


def get_folder_path():
    path = input("Percorso folder immagini: ")
    path = os.path.expanduser(path)
    if not os.path.isabs(path):
        path = os.path.abspath(path)
    if not os.path.isdir(path):
        print("Folder non trovata.")
        return get_folder_path()
    return path



def load_dicom_volume(folder):
    import pydicom
    from glob import glob
    files = sorted(glob(os.path.join(folder, '*.dcm')))
    if not files:
        raise ValueError('Nessun file DICOM trovato nella cartella.')
    # Ordina per InstanceNumber se disponibile
    slices = []
    for f in files:
        ds = pydicom.dcmread(f)
        slices.append((ds, ds.get('InstanceNumber', 0)))
    slices.sort(key=lambda x: x[1])
    vol = np.stack([s[0].pixel_array for s in slices], axis=0)
    # Normalizza a uint8 se necessario
    if vol.dtype != np.uint8:
        vol = ((vol - vol.min()) / (vol.max() - vol.min()) * 255).astype(np.uint8)
    return vol

def load_image(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".dcm":
        ds = pydicom.dcmread(path)
        img = ds.pixel_array
        return img
    else:
        img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError(f"Impossibile caricare {path}")
        return img


def run_processor(processor_name, img):
    module_path, class_name = PROCESSORS[processor_name].rsplit('.', 1)
    module = importlib.import_module(module_path)
    proc_class = getattr(module, class_name)
    # Parametri ottimali per overlay
    if processor_name == "ThresholdCCL":
        proc = proc_class(threshold=160, min_area_px=20000, side="left")
    elif processor_name == "OtsuBorder":
        proc = proc_class(sigma=1.5, min_size_px=20000, closing_radius=7)
    elif processor_name == "EdgeMorph":
        proc = proc_class(window_center=-600, window_width=1500, min_blob_px=30000, closing_kernel=7)
    elif processor_name == "LungMask":
        proc = proc_class(air_thr=200, keep_n=2, close_k=7)
    elif processor_name == "LiverParenchyma":
        proc = proc_class(hu_min=30, hu_max=120, body_thr=-200, grow_tol=30, min_liver_px=35000, close_r=4)
    elif processor_name == "LiverCCSimple":
        proc = proc_class(thr=110, median_k=9, close_k=7, min_area_px=20000, side="left")
    else:
        proc = proc_class()
    result = proc.run(img)
    return result


def show_result(result, img, img_path, processor):
    from utils.viz import overlay_mask
    mask = result["mask"]
    overlay = overlay_mask(img, mask)
    cv2.imshow("overlay", overlay)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    # Salva anche il file
    from pathlib import Path
    result_dir = Path(__file__).parent / "result" / processor
    result_dir.mkdir(parents=True, exist_ok=True)
    base_name = Path(img_path).stem
    out_path = result_dir / f"{base_name}_processed.png"
    cv2.imwrite(str(out_path), overlay)
    print(f"Risultato salvato: {out_path}")


def main():
    processor = None
    mode = None
    while True:
        print_menu(processor, mode)
        choice = input("Scegli opzione: ")
        if choice == "1":
            processor = choose_processor()
        elif choice == "2":
            mode = choose_mode()
        elif choice == "3":
            try:
                if not processor:
                    processor = choose_processor()
                if not mode:
                    mode = choose_mode()
                if processor == "LiverParenchyma":
                    print("Seleziona la cartella con la serie DICOM (TC 3D)...")
                    folder = get_folder_path()
                    vol = load_dicom_volume(folder)
                    result = run_processor(processor, vol)
                    # Salva la slice centrale come overlay
                    z = vol.shape[0] // 2
                    show_result(result, vol[z], f"{folder}/slice{z}", processor)
                elif mode == "slice":
                    img_path = get_image_path()
                    img = load_image(img_path)
                    result = run_processor(processor, img)
                    show_result(result, img, img_path, processor)
                else:
                    folder = get_folder_path()
                    images = glob.glob(os.path.join(folder, "*.png")) + glob.glob(os.path.join(folder, "*.jpg"))
                    for img_path in images:
                        img = load_image(img_path)
                        result = run_processor(processor, img)
                        show_result(result, img, img_path, processor)
            except Exception as e:
                print(f"Errore: {e}")
        elif choice == "4":
            print("Uscita.")
            break
        else:
            print("Scelta non valida.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n:( Test menu interrotto. Alla prossima!")
