# What BeCoMe does

BeCoMe turns a panel's disagreement into one number you can defend, and tells you how much the
disagreement cost.

## The problem it solves

Ask thirteen experts how much arable land a country should convert to flood plains and you get
thirteen answers, most of them ranges rather than single figures. On one Czech panel the
hydrologists recommended converting 37 to 50 percent. The land owners, whose fields those would
be, said 0 to 4. Both groups had reasons.

The usual move is to average everything, and it fails quietly. The plain average of that panel is
about 20 percent: far too little for the hydrologists, ruinous for the farmers, and not one of the
thirteen would defend it. It is also fragile. Add one more strong opinion at either end and the
answer moves again.

Averaging also throws away the ranges. An expert who says "sixty, could be forty to eighty" and one
who says "sixty, give or take two" have told you different things, and a mean of single numbers
cannot hear the difference.

## How it answers

Each expert gives three numbers rather than one: the lowest value they would accept, the value they
consider most likely, and the highest. That is a fuzzy triangular number, and it lets someone say
"around forty, but I could live with thirty-seven" without claiming a precision they do not have.

The method then computes two things the panel already implies. The **average** shows where the
opinions sit in aggregate. The **median** shows where the middle of the panel sits, and it barely
moves when one person takes an extreme position. BeCoMe takes the midpoint of the two, and reports
the distance between them as a separate number.

That second number is the part most methods leave out. It says how far apart the panel was, so a
compromise from a divided room cannot be quoted as if it came from a unanimous one.

## When it fits

It fits when several people who know something must produce one figure, and when their uncertainty
is real rather than a formality. Budget allocation across departments. How much of a policy to
adopt. Any question where "about forty, but it depends" is a more honest answer than "forty".

It fits badly when there is a right answer someone could look up, when one person's judgment
should win outright, or when the question is a choice between options rather than a quantity. For
agreement questions it has a mode of its own, described in
[running a decision](running-a-decision.md).

## Where it comes from

The method was published in 2021 by researchers at the Czech University of Life Sciences Prague:

Vrana, I., Tyrychtr, J., & Pelikán, M. (2021). BeCoMe: Easy-to-implement optimized method for best-compromise group decision making: Flood-prevention and COVID-19 case studies. *Environmental Modelling & Software*, 136, 104953. https://doi.org/10.1016/j.envsoft.2020.104953

This is an independent implementation of that paper wrapped in a web application, so a panel can
run it without writing code. The [method description](../method-description.md) gives the
mathematics in full, with worked formulas.

Ready to try it? [Getting started](getting-started.md) takes about ten minutes, and your account
arrives with the flood panel above already loaded.
