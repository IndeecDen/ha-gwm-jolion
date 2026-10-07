package ru.jolion.locator;

import android.content.Context;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@org.robolectric.annotation.Config(sdk=27, manifest=org.robolectric.annotation.Config.NONE)
public class SecretStoreTest {
    @Test public void unreadableEncryptedIdentityIsNeverReplaced() {
        Context c=RuntimeEnvironment.getApplication();
        Config.prefs(c).edit().clear().putString("key","ks1:unreadable").commit();
        assertEquals("",Config.key(c));
        assertEquals("ks1:unreadable",Config.prefs(c).getString("key",""));
        assertTrue(Config.prefs(c).contains("secret_error"));
    }
    @Test public void legacyIdentitySurvivesMigrationAndFreshIdentityIsStable() {
        Context c=RuntimeEnvironment.getApplication();
        Config.prefs(c).edit().clear().putString("key","legacy-identity").commit();
        assertEquals("legacy-identity",Config.key(c));
        Config.prefs(c).edit().clear().commit();
        String key=Config.key(c);
        assertEquals(48,key.length());
        assertEquals(key,Config.key(c));
    }
}
