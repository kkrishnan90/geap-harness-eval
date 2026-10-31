package com.gridline.telemetry.buffer;

import com.gridline.telemetry.model.Reading;
import java.util.ArrayDeque;
import java.util.Objects;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.locks.Condition;
import java.util.concurrent.locks.ReentrantLock;

/** Thread-safe bounded FIFO between the ingest threads and the aggregation consumer. */
public class BoundedReadingBuffer {
    private final int capacity;
    private final OverflowPolicy policy;
    private final ArrayDeque<Reading> queue;
    private final ReentrantLock lock = new ReentrantLock();
    private final Condition notFull = lock.newCondition();
    private long dropped;
    private long rejected;

    public BoundedReadingBuffer(int capacity, OverflowPolicy policy) {
        if (capacity <= 0) throw new IllegalArgumentException("capacity must be positive");
        this.capacity = capacity;
        this.policy = Objects.requireNonNull(policy, "policy");
        this.queue = new ArrayDeque<>(capacity);
    }

    public boolean offer(Reading r, long timeout, TimeUnit unit) throws InterruptedException {
        Objects.requireNonNull(r, "reading");
        lock.lockInterruptibly();
        try {
            if (queue.size() < capacity) {
                queue.addLast(r);
                return true;
            }
            switch (policy) {
                case DROP_OLDEST:
                    queue.pollFirst();
                    dropped++;
                    queue.addLast(r);
                    return true;
                case REJECT:
                    rejected++;
                    return false;
                case BLOCK:
                default:
                    long nanos = unit.toNanos(timeout);
                    while (queue.size() >= capacity) {
                        if (nanos <= 0) {
                            rejected++;
                            return false;
                        }
                        nanos = notFull.awaitNanos(nanos);
                    }
                    queue.addLast(r);
                    return true;
            }
        } finally {
            lock.unlock();
        }
    }

    /** Oldest reading, or null if empty. Never blocks. */
    public Reading poll() {
        lock.lock();
        try {
            Reading r = queue.pollFirst();
            if (r != null) notFull.signal();
            return r;
        } finally {
            lock.unlock();
        }
    }

    public int size() {
        lock.lock();
        try {
            return queue.size();
        } finally {
            lock.unlock();
        }
    }

    public int capacity() { return capacity; }

    public OverflowPolicy policy() { return policy; }

    public long droppedCount() {
        lock.lock();
        try {
            return dropped;
        } finally {
            lock.unlock();
        }
    }

    public long rejectedCount() {
        lock.lock();
        try {
            return rejected;
        } finally {
            lock.unlock();
        }
    }
}
