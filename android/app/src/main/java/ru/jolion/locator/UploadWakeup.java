package ru.jolion.locator;

/** Remember connectivity changes that arrive during an upload. Caller holds its lock. */
final class UploadWakeup {
    private long revision;
    void networkAvailable() { revision++; }
    long begin() { return revision; }
    long nextDelay(long startedAt, long backoff) { return startedAt == revision ? backoff : 0; }
}
