package ru.jolion.locator;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import static org.junit.Assert.*;

/** The upload interval is driver input, so a typo must be refused, not guessed. */
@RunWith(RobolectricTestRunner.class)
// Fully qualified on purpose: importing org.robolectric.annotation.Config would
// shadow the app's own ru.jolion.locator.Config.
@org.robolectric.annotation.Config(sdk = 27)
public class IntervalTest {
    @Test public void acceptsTheWholeAdvertisedRange() {
        for (int seconds : new int[]{5, 6, 30, 299, 300})
            assertEquals(Integer.valueOf(seconds), Config.parseInterval(String.valueOf(seconds)));
    }

    @Test public void trimsSurroundingWhitespace() {
        assertEquals(Integer.valueOf(45), Config.parseInterval("  45 "));
    }

    @Test public void emptyFieldFallsBackToTheDefault() {
        assertEquals(Integer.valueOf(Config.DEFAULT_INTERVAL_SECONDS), Config.parseInterval(""));
        assertEquals(Integer.valueOf(Config.DEFAULT_INTERVAL_SECONDS), Config.parseInterval("   "));
    }

    @Test public void rejectsValuesOutsideTheRange() {
        for (String raw : new String[]{"4", "0", "-30", "301", "1000", "4.9", "abc", "30s", "1e3"})
            assertNull("должно быть отклонено: " + raw, Config.parseInterval(raw));
    }

    @Test public void rejectsNullRatherThanCrashing() {
        assertNull(Config.parseInterval(null));
    }

    @Test public void storedIntervalFallsBackWhenThePreferenceIsUnusable() {
        android.content.Context context = RuntimeEnvironment.getApplication();
        Config.prefs(context).edit().clear().commit();
        assertEquals(Config.DEFAULT_INTERVAL_SECONDS, Config.intervalSeconds(context));
        Config.prefs(context).edit().putString("interval", "120").commit();
        assertEquals(120, Config.intervalSeconds(context));
        // A hand-edited or corrupted preference must not stop the uploader.
        Config.prefs(context).edit().putString("interval", "9999").commit();
        assertEquals(Config.DEFAULT_INTERVAL_SECONDS, Config.intervalSeconds(context));
        Config.prefs(context).edit().clear().commit();
    }

    /**
     * Regression: an earlier build stored the interval with {@code putInt} while
     * every reader asked {@code getString}. That combination throws
     * {@link ClassCastException} instead of returning the default, which killed the
     * tracking service on its first upload and crashed the settings screen on every
     * later launch. Writing the value the way the uploader does and reading it back
     * is the only check that catches a writer/reader type disagreement.
     */
    @Test public void intervalSurvivesTheTypeTheSettingsScreenWrites() {
        android.content.Context context = RuntimeEnvironment.getApplication();
        Config.prefs(context).edit().clear().commit();
        // Mirror MainActivity.save(): the screen writes a string.
        Config.prefs(context).edit().putString("interval", Integer.toString(90)).commit();
        assertEquals(90, Config.intervalSeconds(context));
        // An int left behind by an older build must be read, not crash the service.
        Config.prefs(context).edit().putInt("interval", 60).commit();
        assertEquals(60, Config.intervalSeconds(context));
        Config.prefs(context).edit().putLong("interval", 45L).commit();
        assertEquals(45, Config.intervalSeconds(context));
        Config.prefs(context).edit().clear().commit();
    }
}
