import pandas as pd
import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import confusion_matrix, classification_report
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import EarlyStopping
import joblib
import os

# --- Config ---
DATASET_PATH = "eye_dataset2.csv"  # dataset file
ALL_FEATURES = [
    'cnn_pca1', 'AVR', 'vessel_redness', 'sclera_mean_hue',
    'AV_sat_diff', 'tortuosity', 'sclera_redness', 'vessel_density',
    'perivascular_contrast', 'pulse_std'
]
TARGET_COL = 'blood_group'

# --- Step 1: Load Dataset ---
try:
    df = pd.read_csv(DATASET_PATH)
except FileNotFoundError:
    print(f"Error: '{DATASET_PATH}' not found.")
    exit()

# --- Step 2: Clean Data ---
df_clean = df.dropna(subset=ALL_FEATURES + [TARGET_COL])

# --- Step 3: Separate features and target ---
X = df_clean[ALL_FEATURES]
y = df_clean[TARGET_COL]

# --- Step 4: Encode target labels ---
encoder = LabelEncoder()
y_encoded = encoder.fit_transform(y)
y_categorical = to_categorical(y_encoded)

# --- Step 5: Scale features ---
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# --- Step 6: Train-Test Split ---
X_train, X_test, y_train, y_test = train_test_split(
    X_scaled, y_categorical, test_size=0.2, random_state=42, stratify=y_encoded
)
y_test_labels = np.argmax(y_test, axis=1)

# --- Step 7: Build Model ---
model = Sequential([
    Dense(512, activation='relu', input_shape=(X_train.shape[1],)),
    Dropout(0.3),
    Dense(256, activation='relu'),
    Dropout(0.3),
    Dense(128, activation='relu'),
    Dropout(0.2),
    Dense(64, activation='relu'),
    Dropout(0.2),
    Dense(y_categorical.shape[1], activation='softmax')
])

optimizer = Adam(learning_rate=0.0001)
model.compile(optimizer=optimizer, loss='categorical_crossentropy', metrics=['accuracy'])

# --- Step 8: Train Model ---
early_stopping = EarlyStopping(monitor='val_accuracy', patience=20, restore_best_weights=True)

history = model.fit(
    X_train, y_train,
    epochs=200,
    batch_size=32,
    validation_split=0.2,
    callbacks=[early_stopping],
    verbose=1
)

# --- Step 9: Evaluate Model ---
loss, accuracy = model.evaluate(X_test, y_test, verbose=0)
print(f"\n✅ Model Accuracy on Test Data: {accuracy * 100:.2f}%")

# --- Step 10: Save Model, Scaler, Encoder ---
model.save('trained_model.h5')
joblib.dump(scaler, 'scaler.pkl')
joblib.dump(encoder, 'encoder.pkl')
print("\n💾 Saved: trained_model.h5, scaler.pkl, encoder.pkl")

# --- Step 11: Accuracy & Loss Graph ---
plt.style.use('seaborn-v0_8-whitegrid')
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
ax1.plot(history.history['accuracy'], label='Train Accuracy')
ax1.plot(history.history['val_accuracy'], label='Validation Accuracy')
ax1.set_title('Model Accuracy')
ax1.set_xlabel('Epoch')
ax1.set_ylabel('Accuracy')
ax1.legend()

ax2.plot(history.history['loss'], label='Train Loss')
ax2.plot(history.history['val_loss'], label='Validation Loss')
ax2.set_title('Model Loss')
ax2.set_xlabel('Epoch')
ax2.set_ylabel('Loss')
ax2.legend()

plt.savefig('accuracy_loss_graphs.png')
plt.close(fig)

# --- Step 12: Confusion Matrix ---
y_pred_probs = model.predict(X_test, verbose=0)
y_pred_labels = np.argmax(y_pred_probs, axis=1)
cm = confusion_matrix(y_test_labels, y_pred_labels)

plt.figure(figsize=(10, 8))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=encoder.classes_, yticklabels=encoder.classes_)
plt.title('Confusion Matrix')
plt.ylabel('Actual Label')
plt.xlabel('Predicted Label')
plt.savefig('confusion_matrix.png')
plt.close()

# --- Step 13: Classification Report ---
print("\nClassification Report:")
print(classification_report(y_test_labels, y_pred_labels, target_names=encoder.classes_))

# --- Step 14: Feature Pairplot (First 5 Features) ---
sns.pairplot(df_clean, vars=ALL_FEATURES[:5], hue=TARGET_COL, plot_kws={'alpha': 0.6}, diag_kind='hist')
plt.suptitle('Pairplot of First 5 Features by Blood Group', y=1.02)
plt.savefig('feature_pairplot.png')
plt.close()

print("\n✅ Training complete. All files saved successfully.")
