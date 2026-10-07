package ru.jolion.locator;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import android.util.Base64;

/** Small Keystore-backed secret store with migration-safe fallback. */
final class SecretStore {
    private static final String STORE = "AndroidKeyStore";
    private static final String ALIAS = "jolion-locator-secrets";
    private static final String PREFIX = "ks1:";
    private final Context context;
    SecretStore(Context context) { this.context = context.getApplicationContext(); }

    String get(String name, String fallback) {
        synchronized (Config.class) {
        String value = Config.prefs(context).getString(name, "");
        if (value.isEmpty()) return fallback;
        if (!value.startsWith(PREFIX)) {
            put(name, value); // migrate existing installations without changing the API
            return value;
        }
        try {
            byte[] packed = Base64.decode(value.substring(PREFIX.length()), Base64.NO_WRAP);
            byte[] iv = new byte[12];
            System.arraycopy(packed, 0, iv, 0, iv.length);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(128, iv));
            return new String(cipher.doFinal(packed, iv.length, packed.length - iv.length), StandardCharsets.UTF_8);
        } catch (Exception ignored) {
            Config.prefs(context).edit().putString("secret_error", "Не удалось прочитать ключ из Android Keystore. Повторите после разблокировки ГУ.").apply();
            return fallback;
        }
        }
    }

    boolean put(String name, String value) {
        synchronized (Config.class) {
        try {
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            // AndroidKeyStore disallows caller-provided encryption IVs by
            // default. Let the provider generate a fresh random nonce.
            cipher.init(Cipher.ENCRYPT_MODE, key());
            byte[] iv = cipher.getIV();
            byte[] encrypted = cipher.doFinal(value.getBytes(StandardCharsets.UTF_8));
            byte[] packed = new byte[iv.length + encrypted.length];
            System.arraycopy(iv, 0, packed, 0, iv.length);
            System.arraycopy(encrypted, 0, packed, iv.length, encrypted.length);
            return Config.prefs(context).edit().putString(name, PREFIX + Base64.encodeToString(packed, Base64.NO_WRAP)).commit();
        } catch (Exception ignored) {
            return Config.prefs(context).edit().putString(name, value).commit();
        }
        }
    }

    private SecretKey key() throws Exception {
        KeyStore store = KeyStore.getInstance(STORE); store.load(null);
        if (!store.containsAlias(ALIAS)) {
            KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, STORE);
            generator.init(new KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());
            generator.generateKey();
        }
        return ((KeyStore.SecretKeyEntry) store.getEntry(ALIAS, null)).getSecretKey();
    }
}
