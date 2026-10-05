p = '/app/frontend/src/pages/StarReward.js'
lines = open(p).read().split('\n')  # line N == lines[N-1]


def repl(start, end, new):
    lines[start - 1:end] = new


# bottom-up
repl(877, 880, [])                                    # BRSF TabsContent block
repl(715, 844, ['            <BrsfFramework />'])     # employees body -> merged BRSF
repl(709, 711, [])                                    # BRSF TabsTrigger
repl(673, 698, ['        {activeTab === "teams" && (',
                *lines[673:698],
                '        )}'])                        # filters card: Teams tab only
repl(629, 671, [])                                    # scheduler strip + stat cards
repl(618, 627, [])                                    # header action buttons

open(p, 'w').write('\n'.join(lines))
print('ok')
