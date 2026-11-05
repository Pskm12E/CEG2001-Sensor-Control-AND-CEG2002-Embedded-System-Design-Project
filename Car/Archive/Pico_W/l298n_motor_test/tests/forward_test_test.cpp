#include <cassert>
#include <cstdio>
#include "../forward_test.h"

int main() {
    ForwardTest test;
    assert(!test.running());
    test.update(0, true, -1);
    assert(!test.running()); // Opening a monitor must not start the motors.

    test.update(10, true, 'f');
    assert(test.running());
    test.update(500, true, 'f');
    assert(test.running());
    test.update(1009, true, -1);
    assert(test.running());
    test.update(1010, true, 'f');
    assert(!test.running()); // Repeated f must not extend/restart at the deadline.

    test.update(2000, true, 'F');
    assert(test.running());
    test.update(2001, true, 's');
    assert(!test.running());
    test.update(3000, true, 'f');
    test.update(3001, true, 'S');
    assert(!test.running());

    test.update(4000, true, 'f');
    test.update(4100, false, -1);
    assert(!test.running()); // USB disconnect cancels the pulse.
    test.update(4200, false, 'f');
    assert(!test.running());
    test.update(4300, true, -1);
    assert(!test.running()); // Reconnection must not resume motion.

    const int ignored_commands[] = {'r', 'b', 'l', 'a', 'g', '\r', '\n', ' '};
    for (int command : ignored_commands) {
        test.update(5000, true, command);
        assert(!test.running()); // No reverse/turn/legacy commands.
    }
    test.update(6000, true, 'f');
    assert(test.running());
    test.update(7001, true, -1);
    assert(!test.running());
    printf("PASS: startup, forward pulse, deadline, stop, USB loss and invalid commands\n");
}
