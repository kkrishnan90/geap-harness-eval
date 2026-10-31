package com.gridline.telemetry.buffer;

/** What {@link BoundedReadingBuffer#offer} does when the buffer is full. */
public enum OverflowPolicy {
    /** Wait up to the given timeout for space; give up (return false) afterwards. */
    BLOCK,
    /** Evict the oldest buffered reading to make room; never blocks, always accepts. */
    DROP_OLDEST,
    /** Refuse the new reading immediately (return false). */
    REJECT
}
