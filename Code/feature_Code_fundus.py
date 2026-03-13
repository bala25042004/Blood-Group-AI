import cv2
import numpy as np
from skimage import color, filters, measure
from sklearn.decomposition import PCA
from tensorflow.keras.applications import ResNet50
from tensorflow.keras.applications.resnet50 import preprocess_input
from tensorflow.keras.preprocessing import image
import os
import uuid

def extract_fundus_features(img_path):
    # ---------- 1. Load Image ----------
    img = cv2.imread(img_path)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # ---------- 2. CNN Feature + PCA ----------
    cnn_model = ResNet50(weights='imagenet', include_top=False, pooling='avg')
    img_resized = cv2.resize(img_rgb, (224, 224))
    x = image.img_to_array(img_resized)
    x = np.expand_dims(x, axis=0)
    x = preprocess_input(x)
    cnn_features = cnn_model.predict(x, verbose=0)
    pca = PCA(n_components=1)
    cnn_pca1 = pca.fit_transform(cnn_features)[0, 0]

    # ---------- 3. Vessel Segmentation ----------
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    vessel_enhanced = filters.frangi(gray)
    vessel_mask = vessel_enhanced > 0.01
    vessel_density = np.sum(vessel_mask) / vessel_mask.size

    # Save processed vessel overlay image
    vessel_overlay = np.zeros_like(img_rgb)
    vessel_overlay[vessel_mask] = [0, 255, 0]  # Green color for vessels
    processed_img = cv2.addWeighted(img_rgb, 1, vessel_overlay, 0.5, 0)
    unique_filename = str(uuid.uuid4()) + "_processed_fundus.png"
    save_path = os.path.join('static', 'uploads', unique_filename)
    cv2.imwrite(save_path, cv2.cvtColor(processed_img, cv2.COLOR_RGB2BGR))

    # ---------- 4. AVR ----------
    vessel_labels = measure.label(vessel_mask)
    props = measure.regionprops(vessel_labels)
    widths = [p.major_axis_length for p in props]
    AVR = np.mean(widths) / (np.max(widths) + 1e-5) if widths else 0

    # ---------- 5. Vessel Redness ----------
    vessel_redness = np.mean(img_rgb[:, :, 0][vessel_mask]) if np.any(vessel_mask) else 0

    # ---------- 6. Tortuosity ----------
    tortuosity_values = []
    for p in props:
        if p.perimeter > 0 and p.major_axis_length > 0:
            tortuosity_values.append(p.perimeter / (p.major_axis_length + 1e-5))
    tortuosity = np.mean(tortuosity_values) if tortuosity_values else 0

    # ---------- Output (Only 5 Selected Features) ----------
    features = {
        "fundus_cnn_pca1": float(cnn_pca1),
        "fundus_AVR": float(AVR),
        "fundus_vessel_redness": float(vessel_redness),
        "fundus_tortuosity": float(tortuosity),
        "fundus_vessel_density": float(vessel_density)
    }

    return features, unique_filename
