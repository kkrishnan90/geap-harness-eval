package testkit;

import java.math.BigDecimal;
import java.util.Objects;

/** Minimal assertion helpers (no JUnit available in this build). */
public final class Assert {
    private Assert() {}

    public interface ThrowingRunnable { void run() throws Throwable; }

    public static void fail(String message) { throw new AssertionError(message); }

    public static void assertTrue(boolean cond, String message) { if (!cond) fail(message); }

    public static void assertTrue(boolean cond) { assertTrue(cond, "expected true"); }

    public static void assertFalse(boolean cond, String message) { if (cond) fail(message); }

    public static void assertFalse(boolean cond) { assertFalse(cond, "expected false"); }

    public static void assertEquals(Object expected, Object actual) { assertEquals(expected, actual, ""); }

    public static void assertEquals(Object expected, Object actual, String message) {
        if (!Objects.equals(expected, actual)) {
            fail((message.isEmpty() ? "" : message + ": ") + "expected <" + expected + "> but was <" + actual + ">");
        }
    }

    public static void assertEquals(long expected, long actual) { assertEquals(expected, actual, ""); }

    public static void assertEquals(long expected, long actual, String message) {
        if (expected != actual) {
            fail((message.isEmpty() ? "" : message + ": ") + "expected <" + expected + "> but was <" + actual + ">");
        }
    }

    public static void assertEquals(double expected, double actual, double delta, String message) {
        if (Math.abs(expected - actual) > delta) {
            fail((message.isEmpty() ? "" : message + ": ") + "expected <" + expected + "> but was <" + actual + ">");
        }
    }

    /** Numeric equality for BigDecimal ignoring scale (1.10 == 1.1). */
    public static void assertAmount(String expected, BigDecimal actual, String message) {
        if (actual == null || new BigDecimal(expected).compareTo(actual) != 0) {
            fail((message.isEmpty() ? "" : message + ": ") + "expected amount <" + expected + "> but was <" + actual + ">");
        }
    }

    public static void assertNotNull(Object o, String message) { if (o == null) fail(message); }

    public static void assertNull(Object o, String message) { if (o != null) fail(message + ": expected null but was <" + o + ">"); }

    public static <T extends Throwable> T assertThrows(Class<T> type, ThrowingRunnable r) {
        try {
            r.run();
        } catch (Throwable t) {
            if (type.isInstance(t)) return type.cast(t);
            throw new AssertionError("expected " + type.getName() + " but got " + t, t);
        }
        throw new AssertionError("expected " + type.getName() + " to be thrown");
    }
}
