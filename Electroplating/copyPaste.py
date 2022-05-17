#Section 3

set.seed(1337)

# P(4) = 3/36
# P(11) = 2/36
# P(12) = 1/36
# P(2)= 1/36
# P(5) = 4/36

# a. Based on our lecture notes on theoretical probability, we find that Adam has a 5/36 chance of doubling his money.
# Likewise, whe will have a 6/36= 1/6 chance of losing all the money he bets
print(5/36)
print(6/36)

set.seed(123)

rolls = 1:6

# We must sample with replacement (as we don't take out the dice rolls)
rand_draws= replicate(10000,sample(rolls,2,replace=TRUE))
# Rand draws saves each trial into a column consisting of both rolls. The actual resulting rolls will be seen
# at column 1 and beyond.

print(rand_draws[,1])

#The results of the each of the rolls will be the sum of the two die

n = 10000

results = colSums(rand_draws)
head(results)

# As we have a small amount of discrete outcomes, it may be easier to visualize the data using a barchart
barplot(table(results),col="black",xlab="Sum of Two Dice Rolls",ylab="Frequency",main="Sum of 2 Dice for 10000 Trials")

#Finding empirical probabilities of Adam losing or doubling his money.
sprintf("Percentage that Adam doubled his money: %1.2f%%",sum(results==4|results==11)/n *100)
sprintf("Percentage that Adam lost his money: %1.2f%%",sum(results==2|results==5|results==12)/n *100)
# We get 13.82% of rolls when Adam doubled his money
# We get 16.97% of rolls when Adam lost his money

# By definition, if the two events are disjoint, they cannot be independent (proof in lecture)
# The two events are disjoint, as Adam cannot both double his money and lose all of his money in a single
# roll of two dice

# Mathematical verification that the events of Adam winning money and Adam losing money are not independent
# As the two events are disjoint, the probability that Adam losing and doubling his money is zero.

pDouble = 5/36
pLose = 6/36

print(pDouble*pLose)
# As we know the two events to be disjoint, P(Doubling Money and Losing Money) = 0. However, the calculated probability
# is a nonzero value, therefore the equation for independence "And" probabilities P(A & B) = P(A)P(B) does not hold, therefore
# the two events are not independent.