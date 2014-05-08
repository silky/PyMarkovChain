from __future__ import division
# use cPickle when using python2 for better performance
try:
    import cPickle as pickle
except ImportError:
    import pickle
import logging
import os
import random
import re
from collections import defaultdict

class StringContinuationImpossibleError(Exception):
    pass

# {words: {word: prob}}
db_factory = lambda: defaultdict(lambda: defaultdict(lambda: 1.0, {}))

def wordIter(text, separator='.'):
    """
    An iterator over the 'words' in the given text, as defined by
    the regular expression given as separator.
    """
    exp = re.compile(separator)
    pos = 0
    for occ in exp.finditer(text):
        sub = text[pos:occ.start()].strip()
        if sub:
            yield sub
        pos = occ.start() + 1
    if pos < len(text):
        # take case of the last part
        sub = text[pos:].strip()
        if sub:
            yield sub

class MarkovChain(object):
    def __init__(self, dbFilePath=None):
        self.dbFilePath = dbFilePath
        if not dbFilePath:
            self.dbFilePath = os.path.join(os.path.dirname(__file__), "markovdb")
        try:
            with open(self.dbFilePath, 'rb') as dbfile:
                self.db = db_factory()
        except IOError:
            print('Database file not found, using empty database')
            self.db = db_factory()
        except ValueError:
            print('Database corrupt or unreadable, using empty database')
            self.db = db_factory()

    def generateDatabase(self, textSample, sentenceSep='[.!?\n]', n=2):
        """ Generate word probability database from raw content string """
        # I'm using the database to temporarily store word counts
        textSample = wordIter(textSample, sentenceSep)  # get an iterator for the 'sentences'
        # We're using '' as special symbol for the beginning
        # of a sentence
        self.db[''][''] = 0.0
        for line in textSample:
            words = line.strip().split()  # split words in line
            if len(words) == 0:
                continue
            # first word follows a sentence end
            self.db[""][words[0]] += 1

            for order in range(1, n+1):
                for i in range(len(words) - 1):
                    if i + order >= len(words):
                        continue
                    word = tuple(words[i:i + order])
                    self.db[word][words[i + order]] += 1

                # last word precedes a sentence end
                self.db[tuple(words[len(words) - order:len(words)])][""] += 1

        # We've now got the db filled with parametrized word counts
        # We still need to normalize this to represent probabilities
        for word in self.db:
            wordsum = 0
            for nextword in self.db[word]:
                wordsum += self.db[word][nextword]
            if wordsum != 0:
                for nextword in self.db[word]:
                    self.db[word][nextword] /= wordsum
        # Now we dump the db to disk
        return self.dumpdb()

    def dumpdb(self):
        try:
            with open(self.dbFilePath, 'wb') as dbfile:
                pickle.dump(self.db, dbfile)
            # It looks like db was written successfully
            return True
        except IOError:
            logging.WARN('Database file could not be written')
            return False

    def generateString(self):
        """ Generate a "sentence" with the database of known text """
        return self._accumulateWithSeed('')

    def generateStringWithSeed(self, seed):
        """ Generate a "sentence" with the database and a given word """
        # using str.split here means we're contructing the list in memory
        # but as the generated sentence only depends on the last word of the seed
        # I'm assuming seeds tend to be rather short.
        words = seed.split()
        if len(words) > 0 and words[len(words) - 1] in self.db:
            sen = ''
            if len(words) > 1:
                sen = words[0]
                for i in range(1, len(words) - 1):
                    sen = sen + ' ' + words[i]
                sen = sen + ' '
            return sen + self._accumulateWithSeed(words[len(words) - 1])
        raise StringContinuationImpossibleError()

    def _accumulateWithSeed(self, seed):
        """ Accumulate the generated sentence with a given single word as a seed """
        nextWord = self._nextWord(seed)
        sentence = [seed] if seed else []
        while nextWord:
            sentence.append(nextWord)
            nextWord = self._nextWord(nextWord)
        return ' '.join(sentence)

    def _nextWord(self, lastword):
        probmap = self.db[lastword]
        sample = random.random()
        # since rounding errors might make us miss out on some words
        maxprob = 0.0
        maxprobword = ""
        for candidate in probmap:
            # remember which word had the highest probability
            # this is the word we'll default to if we can't find anythin else
            if probmap[candidate] > maxprob:
                maxprob = probmap[candidate]
                maxprobword = candidate
            if sample > probmap[candidate]:
                sample -= probmap[candidate]
            else:
                return candidate
        # getting here means we haven't found a matching word. :(
        return maxprobword
