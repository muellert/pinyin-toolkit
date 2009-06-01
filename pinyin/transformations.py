#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pinyin import *

"""
Colorize readings according to the reading in the Pinyin.
* 2009 rewrites by Max Bolingbroke <batterseapower@hotmail.com>
* 2009 original version by Nick Cook <nick@n-line.co.uk> (http://www.n-line.co.uk)
"""
class Colorizer(object):
    tonecolors = {
        1 : u"#ff0000",
        2 : u"#ffaa00",
        3 : u"#00aa00",
        4 : u"#0000ff",
        5 : u"#545454"
      }
     
    def colorize(self, tokens):
        output = TokenList()
        for token in tokens:
            if hasattr(token, "tone"):
                output.append(u'<span style="color:' + self.tonecolors.get(token.tone) + u'">')
                output.append(token)
                output.append(u'</span>')
            else:
                output.append(token)
        
        return output

"""
Output audio reading corresponding to a textual reading.
* 2009 rewrites by Max Bolingbroke <batterseapower@hotmail.com>
* 2009 modifications by Nick Cook <nick@n-line.co.uk> (http://www.n-line.co.uk)
"""
class PinyinAudioReadings(object):
    def __init__(self, available_media, audioextensions):
        self.available_media = available_media
        self.audioextensions = audioextensions
    
    def mediafor(self, basename):
        # Check all possible extensions in order of priority
        for extension in self.audioextensions:
            name = basename + extension
            if name in self.available_media:
                return self.available_media[name]
        
        # No suitable media existed! Return a prompt for the user to download the files [can turn audiogen off if they don't want to]
        return "[Media Error - Click on 'Tools' -> 'Download Mandarin Text-to-Speech Audio Fils']"
    
    def audioreading(self, tokens):
        output = u""
        for token in tokens:
            # Remove the 儿 （r) from pinyin [too complicated to handle automatically].
            # Also skip anything that doesn't look like pinyin, such as English words
            if type(token) != Pinyin or token.numericformat(hideneutraltone=False) == "r5":
                continue
            
            # Find possible base sounds we could accept
            possiblebases = [token.numericformat(hideneutraltone=False)]
            if token.tone == 5:
                # Sometimes we can replace tone 5 with 4 in order to deal with lack of '[xx]5.ogg's
                possiblebases.extend([token.word, token.word + '4'])
            
            # Find path to first suitable media in the possibilty list
            for possiblebase in possiblebases:
                media = self.mediafor(possiblebase)
                if media:
                    break
            
            # If we've managed to find some media, we can put it into the output:
            if media:
                output += '[sound:' + media +']'
        
        return output


# Testsuite
if __name__=='__main__':
    import unittest
    import dictionary
    
    dictionary = dictionary.PinyinDictionary.load("English")
    
    class TestColorizer(unittest.TestCase):
        def testRSuffix(self):
            self.assertEqual(self.colorize(u"哪兒"), '<span style="color:#00aa00">na3</span><span style="color:#545454">r</span>')
        
        def testColorize(self):
            self.assertEqual(self.colorize(u"妈麻马骂吗"),
                '<span style="color:#ff0000">ma1</span> <span style="color:#ffaa00">ma2</span> ' +
                '<span style="color:#00aa00">ma3</span> <span style="color:#0000ff">ma4</span> ' +
                '<span style="color:#545454">ma</span>')
    
        def testMixedEnglishChinese(self):
            self.assertEqual(self.colorize(u'Small 小 - Horse'),
                'Small <span style="color:#00aa00">xiao3</span> - Horse')
        
        def testPunctuation(self):
            self.assertEqual(self.colorize(u'小小!'),
                '<span style="color:#00aa00">xiao3</span> <span style="color:#00aa00">xiao3</span>!')
    
        # Test helpers
        def colorize(self, what):
            return Colorizer().colorize(dictionary.reading(what)).flatten()
    
    class TestColorizer(unittest.TestCase):
        def testColorize(self):
            self.assertEqual(self.colorize(u"妈麻马骂吗"),
                u'<span style="color:#ff0000">妈</span> <span style="color:#ffaa00">麻</span> ' +
                u'<span style="color:#00aa00">马</span> <span style="color:#0000ff">骂</span> ' +
                u'<span style="color:#545454">吗</span>')
    
        def testMixedEnglishChinese(self):
            self.assertEqual(self.colorize(u'Small 小 - Horse'),
                u'Small <span style="color:#00aa00">小</span> - Horse')
        
        def testPunctuation(self):
            self.assertEqual(self.colorize(u'小小!'),
                u'<span style="color:#00aa00">小</span> <span style="color:#00aa00">小</span>!')
    
        # Test helpers
        def colorize(self, what):
            return Colorizer().colorize(dictionary.reading(what)).flatten()
    
    class TestPinyinAudioReadings(unittest.TestCase):
        default_raw_available_media = ["na3.mp3", "ma4.mp3", "xiao3.mp3", "ma3.mp3", "ci2.mp3", "dian3.mp3",
                                       "a4.mp3", "nin2.mp3", "ni3.ogg", "hao3.ogg", "gen1.ogg", "gen1.mp3"]
        
        def testRSuffix(self):
            self.assertEqual(self.audioreading(u"哪兒"), "[sound:na3.mp3]")
        
        def testFifthTone(self):
            self.assertEqual(self.audioreading(u"的", raw_available_media=["de5.mp3", "de.mp3", "de4.mp3"]), "[sound:de5.mp3]")
            self.assertEqual(self.audioreading(u"了", raw_available_media=["le4.mp3", "le.mp3"]), "[sound:le.mp3]")
            self.assertEqual(self.audioreading(u"吗", raw_available_media=["ma4.mp3"]), "[sound:ma4.mp3]")
            
        def testJunkSkipping(self):
            self.assertEqual(self.audioreading(u"Washington ! ! !"), "")
        
        def testMultipleCharacters(self):
            self.assertEqual(self.audioreading(u"小马词典"), "[sound:xiao3.mp3][sound:ma3.mp3][sound:ci2.mp3][sound:dian3.mp3]")
        
        def testMixedEnglishChinese(self):
            self.assertEqual(self.audioreading(u"啊 The Small 马 Dictionary"), "[sound:a4.mp3][sound:ma3.mp3]")
        
        def testPunctuation(self):
            self.assertEqual(self.audioreading(u"您 (pr.)"), "[sound:nin2.mp3]")
        
        def testSecondaryExtension(self):
            self.assertEqual(self.audioreading(u"你好"), "[sound:ni3.ogg][sound:hao3.ogg]")
    
        def testMixedExtensions(self):
            self.assertEqual(self.audioreading(u"你马"), "[sound:ni3.ogg][sound:ma3.mp3]")
    
        def testPriority(self):
            self.assertEqual(self.audioreading(u"根"), "[sound:gen1.mp3]")
    
        # Test helpers
        def audioreading(self, what, raw_available_media=default_raw_available_media):
            available_media = dict([(filename, filename) for filename in raw_available_media])
            return PinyinAudioReadings(available_media, [".mp3", ".ogg"]).audioreading(dictionary.reading(what))
    
    unittest.main()