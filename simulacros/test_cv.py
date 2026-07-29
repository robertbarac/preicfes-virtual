import cv2
import sys
import os
import numpy as np

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import utils_omr


def probar_imagen(image_path):
    print(f"\nIniciando OMR en: {image_path}")
    print("-" * 60)

    warped_blocks, img, imgGray, _, _, imgContours, _ = utils_omr.alinear_documento(image_path)
    img_a_procesar = warped_blocks[0]

    imgThresh, img_debug_ovalos, ovalos = utils_omr.encontrar_ovalos(img_a_procesar)

    print(f"Óvalos detectados: {len(ovalos)}")

    respuestas = utils_omr.agrupar_y_evaluar_ovalos(ovalos, imgThresh)

    print("\n" + "=" * 60)
    print(f"SECUENCIA DE RESPUESTAS FINALES ({len(respuestas)} preguntas):")
    print("".join(respuestas))
    print("=" * 60 + "\n")

    # Guardar debug visual
    out_dir = "cv_prototypes"
    os.makedirs(out_dir, exist_ok=True)

    # Imagen grande solo de detección de óvalos (para diagnóstico)
    cv2.imwrite(os.path.join(out_dir, "debug_ovalos.jpg"), img_debug_ovalos)

    thresh_color = cv2.cvtColor(imgThresh, cv2.COLOR_GRAY2BGR)

    imageArray = (
        [img, imgGray, imgGray],
        [imgContours, img_debug_ovalos, thresh_color]
    )
    stackedImages = utils_omr.stackImages(imageArray, 0.6)  # 0.6 → más legible
    out_path = os.path.join(out_dir, "debug_reciente.jpg")
    cv2.imwrite(out_path, stackedImages)
    print(f"=> Debug visual guardado en: '{out_path}'")
    print(f"=> Óvalos (imagen grande): 'cv_prototypes/debug_ovalos.jpg'")


    if "--headless" not in sys.argv:
        cv2.imshow("OMR Debug", stackedImages)
        print("Presiona cualquier tecla para cerrar...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    else:
        print("[Modo Headless] omitiendo apertura de ventana.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python test_cv.py /ruta/a/imagen.jpg [--headless]")
    else:
        try:
            probar_imagen(sys.argv[1])
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error mortal: {e}")
