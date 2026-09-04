# Running a decision

An expert answers your question with three numbers instead of one. That is the whole idea, and
everything on this page follows from it.

## Why three numbers

Ask someone for a budget figure and they will give you one, because you asked for one. Ask them how
confident they are and they will tell you something quite different: "around sixty, but it could be
forty, and I would not argue with eighty."

The second answer is the true one. The first threw away the part that matters, which is the width.
An expert who says 60 with a range of 40 to 80 and an expert who says 60 with a range of 58 to 62
have said different things, and a method that averages single numbers cannot hear the difference.

An opinion here has three components. The **lower** bound is the pessimistic end of what is
realistic, the **peak** is the single most likely value, and the **upper** bound is the optimistic
end. They must satisfy `lower ≤ peak ≤ upper`, and the form will refuse anything else.

![The opinion form: position, and the three estimate fields](img/project-opinions.png)

## The three ways to answer

**A fuzzy triangular number** is the normal case, and the one to reach for by default. Enter three
different values: `(40, 60, 80)` says "sixty, and I would accept anything from forty to eighty".

Widening your range does not weaken your vote, which is worth saying because most people assume the
opposite. Take a panel of four and vary only the fourth opinion's width, keeping its peak at 60:

| Fourth opinion | Compromise | Center |
|---|---|---|
| `(58, 60, 62)` | `(38.50, 47.50, 56.50)` | 47.50 |
| `(40, 60, 80)` | `(33.75, 47.50, 61.25)` | 47.50 |
| `(20, 60, 100)` | `(26.25, 47.50, 68.75)` | 47.50 |

The center does not move. What changes is the width of the answer: an honest range makes the
group's uncertainty visible instead of hiding it. So state the range you actually believe. You are
not spending influence by admitting doubt.

**A crisp number** is for the expert who is genuinely certain. Enter the same value three times:
`(50, 50, 50)`. It is a triangle with no width, and the method treats it as one. Do not use it to
mean "I do not want to think about the range". A false certainty carries more weight than it has
earned.

**An agreement answer** is what the method offers for "should we" questions instead of "how much"
ones, on a scale of 0 to 100 with no unit. It is described under
[reading the result](reading-the-result.md), and it is not usable yet: the create form will not
make such a project. Everything above applies to the quantities you can actually ask about today.

## When the result appears

As soon as there is something to compute. The result updates every time an opinion arrives, so a
half-answered panel gives a real answer for the experts who have answered so far.

That is worth using rather than waiting out. If the compromise swings hard when the fourth expert
answers, you have learned something about your panel that the final number will hide.

Next: [reading the result](reading-the-result.md).
