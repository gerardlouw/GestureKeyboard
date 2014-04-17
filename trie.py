#!/usr/bin/python
#By Steve Hanov, 2011. Released to the public domain

class TrieNode:
    def __init__(self):
        self.word = None
        self.value = None
        self.children = {}

class Trie:
    def __init__(self):
        self.trie = TrieNode()
        self.words = []

    def __getitem__(self, word):
        node = self.trie
        for letter in word:
            if letter not in node.children:
                return None
            node = node.children[letter]
        return node.value
    
    def __setitem__(self, word, value):
        node = self.trie
        for letter in word:
            if letter not in node.children: 
                node.children[letter] = TrieNode()
            node = node.children[letter]
        if node.word != word:
            self.words.append(word)
        node.word = word
        node.value = value
    
    def __iter__(self):
        return iter(self.words)
        #S = []
        #S.append(self.trie)
        #while len(S) > 0:
        #    node = S.pop()
        #    if node.word is not None:
        #        yield node.word
        #    S.extend(node.children.values())
    
    def search_correction(self, word, maxCost):
        currentRow = range( len(word) + 1 )
        results = []
        for letter in self.trie.children:
            self._searchRecursive( self.trie.children[letter], letter, word, currentRow, 
                results, maxCost )
        totalResults = [(n.word, v) for n, v in results if n.word is not None]
        return totalResults
    
    def search_prediction(self, word, maxCost):
        currentRow = range( len(word) + 1 )
        results = []
        for letter in self.trie.children:
            self._searchRecursive( self.trie.children[letter], letter, word, currentRow, 
                results, maxCost )
        totalResults = {}
        for node, cost in results:
            S = [node]
            while len(S) > 0:
                n = S.pop()
                if n.word is not None and (n.word not in totalResults or totalResults[n.word] > cost):
                    totalResults[n.word] = cost
                for child in n.children.values():
                    S.append(child)
        totalResults = totalResults.items()
        return totalResults

    def _searchRecursive(self, node, letter, word, previousRow, results, maxCost):
        columns = len( word ) + 1
        currentRow = [ previousRow[0] + 1 ]
        for column in xrange( 1, columns ):
            insertCost = currentRow[column - 1] + 1
            deleteCost = previousRow[column] + 1
            if word[column - 1] != letter:
                replaceCost = previousRow[ column - 1 ] + 1
            else:                
                replaceCost = previousRow[ column - 1 ]

            currentRow.append( min( insertCost, deleteCost, replaceCost ) )
        if currentRow[-1] <= maxCost:
            results.append( (node, currentRow[-1] ) )
        if min( currentRow ) <= maxCost:
            for letter in node.children:
                self._searchRecursive( node.children[letter], letter, word, currentRow, 
                    results, maxCost )
