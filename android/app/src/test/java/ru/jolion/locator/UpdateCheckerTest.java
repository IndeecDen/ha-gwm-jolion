package ru.jolion.locator;

import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=27, manifest=Config.NONE)
public class UpdateCheckerTest {
    @Test public void comparesReleaseVersionsWithBetaSuffixes() {
        assertTrue(UpdateChecker.compareVersions("0.2.0-beta.3", "0.2.0-beta.2") > 0);
        assertTrue(UpdateChecker.compareVersions("0.2.0", "0.2.0-beta.9") > 0);
        assertEquals(0, UpdateChecker.compareVersions("v0.2.0".substring(1), "0.2.0"));
    }
    @Test public void selectsApkAndChecksumAssets() throws Exception {
        JSONObject release=new JSONObject("{\"tag_name\":\"v0.2.0-beta.3\",\"body\":\"notes\",\"assets\":["
            +"{\"name\":\"README.txt\"},"
            +"{\"name\":\"Jolion Locator 0.2.0.apk\",\"browser_download_url\":\"https://example/apk\",\"size\":12},"
            +"{\"name\":\"SHA256SUMS.txt\",\"browser_download_url\":\"https://example/sums\"}]} ");
        UpdateChecker.Release parsed=UpdateChecker.parseRelease(release);
        assertNotNull(parsed); assertEquals("0.2.0-beta.3", parsed.version); assertEquals(12, parsed.size); assertEquals("https://example/apk", parsed.apkUrl); assertEquals("Jolion Locator 0.2.0.apk", parsed.apkName);
    }
    @Test public void ignoresDraftAndMissingApk() throws Exception {
        assertNull(UpdateChecker.parseRelease(new JSONObject("{\"draft\":true,\"assets\":[]}")));
        assertNull(UpdateChecker.parseRelease(new JSONObject("{\"assets\":[{\"name\":\"notes.txt\"}]}")));
    }
    @Test public void parsesChecksumByExactOrOnlyApkAsset() {
        String hash="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
        assertEquals(hash, UpdateChecker.checksumFromText(hash+"  Jolion Locator 0.2.0.apk\n", "Jolion Locator 0.2.0.apk"));
        assertNull(UpdateChecker.checksumFromText(hash+"  release.apk\n", "cached.apk"));
    }
}
