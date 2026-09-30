package ru.jolion.locator;

import org.junit.Test;
import static org.junit.Assert.*;

public class UploadWakeupTest {
    @Test public void reconnectDuringFailedUploadOverridesBackoff() {
        UploadWakeup wakeup = new UploadWakeup();
        long started = wakeup.begin();
        wakeup.networkAvailable();
        assertEquals(0, wakeup.nextDelay(started, 300000));
        assertEquals(300000, wakeup.nextDelay(wakeup.begin(), 300000));
    }
    @Test public void normalFailureRetainsBackoff() {
        UploadWakeup wakeup = new UploadWakeup();
        wakeup.networkAvailable();
        long started = wakeup.begin();
        assertEquals(10000, wakeup.nextDelay(started, 10000));
    }
}
