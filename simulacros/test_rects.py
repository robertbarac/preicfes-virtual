import cv2
import sys

img = cv2.imread('simulacros/imagenes_muestra/prueba1mayo/RESPUESTA SM3 DISEÑO DE ROBERT_page-0002.jpg')
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
imgThresh = cv2.adaptiveThreshold(
    gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    cv2.THRESH_BINARY_INV, 51, 10
)
contours, _ = cv2.findContours(imgThresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

print("Contornos grandes:")
for c in contours:
    area = cv2.contourArea(c)
    if area > 10000:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.015 * peri, True)
        if len(approx) == 4:
            x, y, w, h = cv2.boundingRect(approx)
            ar = h / float(w)
            print(f"Rect area={area:.0f}, x={x}, y={y}, w={w}, h={h}, ar={ar:.2f}")
