package testkit;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/**
 * Tiny main-based test runner. Usage: java -cp ... testkit.TestRunner com.example.FooTest [...]
 * Prints "RESULT PASS|FAIL <SimpleClassName>.<method>" per test and exits 1 on any failure.
 * Each test runs in its own daemon thread with a timeout, so a hung test fails instead of hanging.
 */
public final class TestRunner {
    public static void main(String[] args) {
        int failed = 0, total = 0;
        for (String className : args) {
            Class<?> cls;
            try {
                cls = Class.forName(className);
            } catch (Throwable t) {
                System.out.println("LOAD ERROR " + className + ": " + t);
                failed++;
                continue;
            }
            List<Method> tests = new ArrayList<>();
            for (Method m : cls.getMethods()) {
                if (m.isAnnotationPresent(Test.class) && m.getParameterCount() == 0) tests.add(m);
            }
            tests.sort(Comparator.comparing(Method::getName));
            for (Method m : tests) {
                total++;
                String id = cls.getSimpleName() + "." + m.getName();
                Throwable err = runOne(cls, m);
                if (err == null) {
                    System.out.println("RESULT PASS " + id);
                } else {
                    failed++;
                    System.out.println("RESULT FAIL " + id);
                    System.out.println("  " + err);
                    StackTraceElement[] st = err.getStackTrace();
                    for (int i = 0; i < Math.min(6, st.length); i++) System.out.println("    at " + st[i]);
                }
                System.out.flush();
            }
        }
        System.out.println("TESTS " + total + " FAILED " + failed);
        System.exit(failed == 0 ? 0 : 1);
    }

    private static Throwable runOne(Class<?> cls, Method m) {
        final Throwable[] box = new Throwable[1];
        Thread t = new Thread(() -> {
            try {
                Object target = Modifier.isStatic(m.getModifiers()) ? null : cls.getDeclaredConstructor().newInstance();
                m.invoke(target);
            } catch (InvocationTargetException e) {
                box[0] = e.getCause();
            } catch (Throwable e) {
                box[0] = e;
            }
        }, "test-" + m.getName());
        t.setDaemon(true);
        t.start();
        long timeout = m.getAnnotation(Test.class).timeoutMillis();
        try {
            t.join(timeout);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        if (t.isAlive()) {
            t.interrupt();
            return new AssertionError("timed out after " + timeout + " ms");
        }
        return box[0];
    }
}
