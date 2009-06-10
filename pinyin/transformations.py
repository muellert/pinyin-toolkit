#!/usr/bin/env python
# -*- coding: utf-8 -*-

import random

from logger import log
from pinyin import *
from utils import *


# Convenience wrapper around the ToneSandhiVisitor
def tonesandhi(token):
    ismono, doer = token.accept(ToneSandhiVisitor())
    return doer(False, ismono, True, False)

"""
Applies tone sandhi. Nick thinks the rules are as follows:
* simple rule: a mono-syllabic word loses it's third tone if followed by another mono-syllabic word
* a monosyllabic word in front of a multi-syllabic word keeps its third tone, the multi-syllabic word changes to 2^x,3
* monosyllabic word after a multi-syllabic word keeps its third tone but the multi-syllabic words lose all of their third tones
* multisylabic words not followed by monosyllabic words convert all third tones except the last into second tones.

See also: <http://en.wikipedia.org/wiki/Standard_Mandarin#Tone_sandhi>. This disagrees with those rules:
* "If the first word is two syllables, and the second word is one syllable, the first two syllables become 2nd tones,
   and the last syllable stays 3rd tone"
  - So ALL of a multisyllabic word should be 3rd tone if it is followed by a monosyllabic one
"""
class ToneSandhiVisitor(TokenVisitor):
    # Each visit method returns a pair of a marker saying whether this particular token
    # could (if enclosed in a Word) be monosyllabic, and a function which when given
    # various information about the syllabic context in which it sits returns new tokens.
    #
    # For those familiar with it, I'm basically making use of lazy functional programming
    # with recursive value definitions (albeit it in a rather clunky format!)
    
    def visitText(self, text):
        return lambda lw, ls, rs, rw: text

    def visitPinyin(self, pinyin):
        return self.visitToned(pinyin, lambda tone: Pinyin(pinyin.word + str(tone)))

    def visitTonedCharacter(self, tonedcharacter):
        return self.visitToned(tonedcharacter, lambda tone: TonedCharacter(unicode(tonedcharacter), tone))

    def visitToned(self, toned, rebuild):
        def do(monobefore, ismono, islastinword, monoafter):
            if toned.tone != 3:
                # Don't modify non-3rd tone things
                return toned
            
            # When do we lose tones?
            print toned, monobefore, ismono, islastinword, monoafter
            shouldusethirdtone = [
                ismono and monoafter,                                   # Mono loses tone if followed by mono
                (not ismono) and (not islastinword) and monobefore,     # Multi loses tone in non-last positions if following mono
                (not ismono) and monoafter,                             # Multi loses tone is all positions if followed by mono
                (not ismono) and (not islastinword) and (not monoafter) # Multi loses tone in non-last positions if not followed by mono
              ]
            
            if any(shouldusethirdtone):
                return rebuild(2)
            else:
                return toned
        
        return True, do

    def visitWord(self, word):
        return lambda lw, ls, rs, rw: word.token.accept(self)(lw, [], [], rw)

    def visitTokenList(self, tokens):
        def do(lw, ls, rs, rw):
            for n, token in enumerate(tokens):
                token.accept(self)(n == 0 and lw or token[n - 1], )
        
        return do


# Convenience wrapper around the TrimErhuaVisitor
def trimerhua(words):
    return [word.concatmap(TrimErhuaVisitor()) for word in words]

class TrimErhuaVisitor(TokenVisitor):
    def visitText(self, text):
        return [text]

    def visitPinyin(self, pinyin):
        if pinyin.iser:
            return []
        else:
            return [pinyin]

    def visitTonedCharacter(self, tonedcharacter):
        if tonedcharacter.iser:
            return []
        else:
            return [tonedcharacter]


# Convenience wrapper around the ColorizerVisitor
def colorize(colorlist, words):
    return [word.concatmap(ColorizerVisitor(colorlist)) for word in words]

"""
Colorize readings according to the reading in the Pinyin.
* 2009 rewrites by Max Bolingbroke <batterseapower@hotmail.com>
* 2009 original version by Nick Cook <nick@n-line.co.uk> (http://www.n-line.co.uk)
"""
class ColorizerVisitor(TokenVisitor):
    def __init__(self, colorlist):
        self.colorlist = colorlist
        log.info("Using color list %s", self.colorlist)
        
    def visitText(self, text):
        return [text]

    def visitPinyin(self, pinyin):
        return self.colorize(pinyin)

    def visitTonedCharacter(self, tonedcharacter):
        return self.colorize(tonedcharacter)
    
    def colorize(self, token):
        return [
            Text(u'<span style="color:' + self.colorlist[token.tone - 1] + u'">'),
            token,
            Text(u'</span>')
          ]

"""
Output audio reading corresponding to a textual reading.
* 2009 rewrites by Max Bolingbroke <batterseapower@hotmail.com>
* 2009 original version by Nick Cook <nick@n-line.co.uk> (http://www.n-line.co.uk)
"""
class PinyinAudioReadings(object):
    def __init__(self, mediapacks, audioextensions):
        self.mediapacks = mediapacks
        self.audioextensions = audioextensions
    
    def audioreading(self, tokens):
        log.info("Requested audio reading for %d tokens", len(tokens))
        
        # Try possible packs to format the tokens. Basically, we
        # don't want to use a mix of sounds from different packs
        bestmediapacksoutputs, bestmediamissingcount = [], len(tokens) + 1
        for mediapack in self.mediapacks:
            log.info("Checking for reading in pack %s", mediapack.name)
            output, mediamissingcount = audioreadingforpack(mediapack, self.audioextensions, trimerhua(tokens))
            
            # We will end up choosing one of the packs that minimizes the number of errors:
            if mediamissingcount == bestmediamissingcount:
                # Just as good as a previous pack, so this is an alternative
                bestmediapacksoutputs.append((mediapack, output))
            elif mediamissingcount < bestmediamissingcount:
                # Strictly better than the previous ones, so this is the new best option
                bestmediapacksoutputs = [(mediapack, output)]
                bestmediamissingcount = mediamissingcount
        
        # Did we get any result at all?
        if len(bestmediapacksoutputs) != 0:
            bestmediapack, bestoutput = random.choice(bestmediapacksoutputs)
            return bestmediapack, bestoutput, (bestmediamissingcount != 0)
        else:
            return None, [], True

# Simple wrapper around the PinyinAudioReadingsVisitor
def audioreadingforpack(mediapack, audioextensions, words):
    visitor = PinyinAudioReadingsVisitor(mediapack, audioextensions)
    [word.accept(visitor) for word in trimerhua(words)]
    return (visitor.output, visitor.mediamissingcount)

class PinyinAudioReadingsVisitor(TokenVisitor):
    def __init__(self, mediapack, audioextensions):
        self.mediapack = mediapack
        self.audioextensions = audioextensions
        
        self.output = []
        self.mediamissingcount = 0
    
    def visitText(self, text):
        pass

    def visitPinyin(self, pinyin):
        # Find possible base sounds we could accept
        possiblebases = [pinyin.numericformat(hideneutraltone=False)]
        if pinyin.tone == 5:
            # Sometimes we can replace tone 5 with 4 in order to deal with lack of '[xx]5.ogg's
            possiblebases.extend([pinyin.word, pinyin.word + '4'])
        elif u"u:" in pinyin.word:
            # Typically u: is written as v in filenames
            possiblebases.append(pinyin.word.replace(u"u:", u"v") + str(pinyin.tone))
    
        # Find path to first suitable media in the possibilty list
        for possiblebase in possiblebases:
            media = self.mediapack.mediafor(possiblebase, self.audioextensions)
            if media:
                break
    
        if media:
            # If we've managed to find some media, we can put it into the output:
            self.output.append(media)
        else:
            # Otherwise, increment the count of missing media we use to determine optimality
            log.warning("Couldn't find media for %s in %s", pinyin, self.mediapack)
            self.mediamissingcount += 1

    def visitTonedCharacter(self, tonedcharacter):
        pass

# Wrapper around the MaskHanziVisitor
def maskhanzi(expression, maskingcharacter, words):
    return [word.map(MaskHanziVisitor(expression, maskingcharacter)) for word in words]

class MaskHanziVisitor(TokenVisitor):
    def __init__(self, expression, maskingcharacter):
        self.expression = expression
        self.maskingcharacter = maskingcharacter
    
    def visitText(self, text):
        return Text(text.replace(self.expression, self.maskingcharacter))

    def visitPinyin(self, pinyin):
        return pinyin

    def visitTonedCharacter(self, tonedcharacter):
        if unicode(tonedcharacter) == self.expression:
            return Text(self.maskingcharacter)
        else:
            return tonedcharacter

# Testsuite
if __name__=='__main__':
    import unittest
    import dictionary
    
    from media import MediaPack
    
    # Shared dictionary
    englishdict = Thunk(lambda: dictionary.PinyinDictionary.load("en"))
    
    # Default tone color list for tests
    colorlist = [
        u"#ff0000",
        u"#ffaa00",
        u"#00aa00",
        u"#0000ff",
        u"#545454"
      ]
    
    class PinyinColorizerTest(unittest.TestCase):
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
            return flatten(colorize(colorlist, englishdict.reading(what)))
    
    class CharacterColorizerTest(unittest.TestCase):
        def testColorize(self):
            self.assertEqual(self.colorize(u"妈麻马骂吗"),
                u'<span style="color:#ff0000">妈</span><span style="color:#ffaa00">麻</span>' +
                u'<span style="color:#00aa00">马</span><span style="color:#0000ff">骂</span>' +
                u'<span style="color:#545454">吗</span>')
    
        def testMixedEnglishChinese(self):
            self.assertEqual(self.colorize(u'Small 小 - Horse'),
                u'Small <span style="color:#00aa00">小</span> - Horse')
        
        def testPunctuation(self):
            self.assertEqual(self.colorize(u'小小!'),
                u'<span style="color:#00aa00">小</span><span style="color:#00aa00">小</span>!')
    
        # Test helpers
        def colorize(self, what):
            return flatten(colorize(colorlist, englishdict.tonedchars(what)))
    
    class PinyinAudioReadingsTest(unittest.TestCase):
        default_raw_available_media = ["na3.mp3", "ma4.mp3", "xiao3.mp3", "ma3.mp3", "ci2.mp3", "dian3.mp3",
                                       "a4.mp3", "nin2.mp3", "ni3.ogg", "hao3.ogg", "gen1.ogg", "gen1.mp3"]
        
        def testRSuffix(self):
            self.assertHasReading(u"哪兒", ["na3.mp3"])
            self.assertHasReading(u"哪儿", ["na3.mp3"])
        
        def testFifthTone(self):
            self.assertHasReading(u"的", ["de5.mp3"], raw_available_media=["de5.mp3", "de.mp3", "de4.mp3"])
            self.assertHasReading(u"了", ["le.mp3"], raw_available_media=["le4.mp3", "le.mp3"])
            self.assertHasReading(u"吗", ["ma4.mp3"], raw_available_media=["ma4.mp3"])
        
        def testNv(self):
            self.assertHasReading(u"女", ["nu:3.mp3"], raw_available_media=["nv3.mp3", "nu:3.mp3", "nu3.mp3"])
            self.assertHasReading(u"女", ["nv3.mp3"], raw_available_media=["nu3.mp3", "nv3.mp3"])
            self.assertMediaMissing(u"女", raw_available_media=["nu3.mp3"])
            
        def testLv(self):
            self.assertHasReading(u"侣", ["lv3.mp3"], raw_available_media=["lv3.mp3"])
            self.assertMediaMissing(u"侣", raw_available_media=["lu3.mp3"])
            self.assertHasReading(u"掠", ["lve4.mp3"], raw_available_media=["lve4.mp3"])
            self.assertMediaMissing(u"掠", raw_available_media=["lue4.mp3"])
        
        def testJunkSkipping(self):
            # NB: NOT a partial reading, because none of the tokens here are Pinyin it doesn't know about
            self.assertHasReading(u"Washington ! ! !", [])
        
        def testMultipleCharacters(self):
            self.assertHasReading(u"小马词典", ["xiao3.mp3", "ma3.mp3", "ci2.mp3","dian3.mp3"])
        
        def testMixedEnglishChinese(self):
            self.assertHasReading(u"啊 The Small 马 Dictionary", ["a4.mp3", "ma3.mp3"])
        
        def testPunctuation(self):
            self.assertHasReading(u"您 (pr.)", ["nin2.mp3"])
        
        def testSecondaryExtension(self):
            self.assertHasReading(u"你好", ["ni3.ogg", "hao3.ogg"])
    
        def testMixedExtensions(self):
            self.assertHasReading(u"你马", ["ni3.ogg", "ma3.mp3"])
    
        def testPriority(self):
            self.assertHasReading(u"根", ["gen1.mp3"])
    
        def testMediaMissing(self):
            self.assertMediaMissing(u"根", raw_available_media=[".mp3"])
    
        def testCaptializationInPinyin(self):
            # NB: 上海 is in the dictionary with capitalized pinyin (Shang4 hai3)
            self.assertHasReading(u"上海", ["shang4.mp3", "hai3.mp3"], raw_available_media=["shang4.mp3", "hai3.mp3"])
        
        def testCapitializationInFilesystem(self):
            self.assertHasReading(u"根", ["GeN1.mP3"], available_media={"GeN1.mP3" : "GeN1.mP3" })
    
        def testDontMixPacks(self):
            packs = [MediaPack("Foo", {"ni3.mp3" : "ni3.mp3", "ma3.mp3" : "ma3.mp3"}), MediaPack("Bar", {"hao3.mp3" : "hao3.mp3"})]
            self.assertHasPartialReading(u"你好马", ["ni3.mp3", "ma3.mp3"], bestpackshouldbe=packs[0], mediapacks=packs)
    
        def testUseBestPack(self):
            packs = [MediaPack("Foo", {"xiao3.mp3" : "xiao3.mp3", "ma3.mp3" : "ma3.mp3"}),
                     MediaPack("Bar", {"ma3.mp3" : "ma3.mp3", "ci2.mp3" : "ci2.mp3", "dian3.mp3" : "dian3.mp3"})]
            self.assertHasPartialReading(u"小马词典", ["ma3.mp3", "ci2.mp3", "dian3.mp3"], bestpackshouldbe=packs[1], mediapacks=packs)
    
        def testRandomizeBestPackOnTie(self):
            pack1 = MediaPack("Foo", {"ni3.mp3" : "PACK1.mp3"})
            pack2 = MediaPack("Bar", {"ni3.mp3" : "PACK2.mp3"})
    
            gotpacks = []
            for n in range(1, 10):
                gotpack, _, _ = PinyinAudioReadings([pack1, pack2], [".mp3", ".ogg"]).audioreading(englishdict.reading(u"你"))
                gotpacks.append(gotpack)
            
            # This test will nondeterministically fail (1/2)^10 = 0.01% of the time
            self.assertTrue(pack1 in gotpacks)
            self.assertTrue(pack2 in gotpacks)
    
        # Test helpers
        def assertHasReading(self, what, shouldbe, **kwargs):
            bestpackshouldbe, mediapack, output, mediamissing = self.audioreading(what, **kwargs)
            self.assertEquals(bestpackshouldbe, mediapack)
            self.assertEquals(output, shouldbe)
            self.assertFalse(mediamissing)
        
        def assertHasPartialReading(self, what, shouldbe, **kwargs):
            bestpackshouldbe, mediapack, output, mediamissing = self.audioreading(what, **kwargs)
            self.assertEquals(bestpackshouldbe, mediapack)
            self.assertEquals(output, shouldbe)
            self.assertTrue(mediamissing)
            
        def assertMediaMissing(self, what, **kwargs):
            bestpackshouldbe, mediapack, output, mediamissing = self.audioreading(what, **kwargs)
            self.assertTrue(mediamissing)
        
        def audioreading(self, what, **kwargs):
            bestpackshouldbe, mediapacks = self.expandmediapacks(**kwargs)
            mediapack, output, mediamissing = PinyinAudioReadings(mediapacks, [".mp3", ".ogg"]).audioreading(englishdict.reading(what))
            return bestpackshouldbe, mediapack, output, mediamissing
        
        def expandmediapacks(self, mediapacks=None, available_media=None, raw_available_media=default_raw_available_media, bestpackshouldbe=None):
            if mediapacks:
                return bestpackshouldbe, mediapacks
            elif available_media:
                pack = MediaPack("Test", available_media)
                return pack, [pack]
            else:
                pack = MediaPack("Test", dict([(filename, filename) for filename in raw_available_media]))
                return pack, [pack]
    
    class ToneSandhiTest(unittest.TestCase):
        def testSimple(self):
            self.assertSandhi(Pinyin("hen3"), Pinyin("hao3"), "hen2hao3")
            self.assertSandhi(Word(Pinyin("hen3")), Word(Pinyin("hao3")), "hen2hao3")
        
        def testMultiMono(self):
            self.assertSandhi(Word(TokenList([Pinyin("bao3"), Pinyin("guan3")])), Word(Pinyin("hao3")), "bao2guan2hao3")
        
        def testMonoMulti(self):
            self.assertSandhi(Word(Pinyin("lao3")), Word(TokenList([Pinyin("bao3"), Pinyin("guan3")])), "lao3bao2guan3")
        
        def testYiFollowedByFour(self):
            self.assertSandhi(Pinyin("yi1"), Pinyin("ding4"), "yi2ding4")
        
        def testYiFollowedByOther(self):
            self.assertSandhi(Pinyin("yi1"), Pinyin("tian1"), "yi4tian1")
            self.assertSandhi(Pinyin("yi1"), Pinyin("nian2"), "yi4nian2")
            self.assertSandhi(Pinyin("yi1"), Pinyin("qi3"), "yi4qi3")
        
        def testYiBetweenTwoWords(self):
            self.assertSandhi(Word(Pinyin("kan4")), Word(Pinyin("yi1")), Word(Pinyin("kan4")), "kan4yikan4")
        
        # NB: don't bother to implement yi1 sandhi that depends on context such as whether we are
        # counting sequentially or using yi1 as an ordinal number
        
        def testBuFollowedByFourth(self):
            self.assertSandhi(Pinyin("bu4"), Pinyin("shi4"), "bu2shi4")
        
        def testBuBetweenTwoWords(self):
            self.assertSandhi(Word(Pinyin("shi4")), Word(Pinyin("bu4")), Word(Pinyin("shi4")), "shi4bushi4")
        
        # Test helpers
        def assertSandhi(self, *args):
            self.assertEquals(flatten(tonesandhi(TokenList(args[:-1]))), args[-1])
    
    class TrimErhuaTest(unittest.TestCase):
        def testTrimErhuaEmpty(self):
            self.assertEquals(flatten(trimerhua([])), u'')

        def testTrimErhuaCharacters(self):
            self.assertEquals(flatten(trimerhua([Word(TonedCharacter(u"一", 1), TonedCharacter(u"瓶", 2), TonedCharacter(u"儿", 5))])), u"一瓶")

        def testTrimErhuaPinyin(self):
            self.assertEquals(flatten(trimerhua([Word(Pinyin(u"yi1"), Pinyin(u"ping2"), Pinyin(u"r5"))])), u"yi1ping2")
            self.assertEquals(flatten(trimerhua([Word(Pinyin(u"yi1")), Word(Pinyin(u"ping2"), Pinyin(u"r5"))])), u"yi1ping2")

        def testDontTrimNonErhua(self):
            self.assertEquals(flatten(trimerhua([Word(TonedCharacter(u"一", 1), TonedCharacter(u"瓶", 2))])), u"一瓶")

        def testTrimSingleErHua(self):
            self.assertEquals(flatten(trimerhua([Word(Pinyin(u'r5'))])), u'')
            self.assertEquals(flatten(trimerhua([Word(TonedCharacter(u'儿', 5))])), u'')
            self.assertEquals(flatten(trimerhua([Word(Pinyin(u'r5'))])), u'')
            self.assertEquals(flatten(trimerhua([Word(TonedCharacter(u'儿', 5))])), u'')
            self.assertEquals(flatten(trimerhua([Word(Pinyin(u'r5'))])), u'')
            self.assertEquals(flatten(trimerhua([Word(TonedCharacter(u'儿', 5))])), u'')

    class MaskHanziTest(unittest.TestCase):
        def testMaskText(self):
            self.assertEquals(maskhanzi("ello", "mask", [Word(Text("World")), Word(Text("Hello!")), Word(Text(" "), Text("Jello"))]),
                              [Word(Text("World")), Word(Text("Hmask!")), Word(Text(" "), Text("Jmask"))])
        
        def testMaskCharacter(self):
            self.assertEquals(maskhanzi("hen", "chicken", [Word(Pinyin("hen3")), Word(TonedCharacter("hen", 3)), Word(TonedCharacter("mhh", 2))]),
                              [Word(Pinyin("hen3")), Word(Text("chicken")), Word(TonedCharacter("mhh", 2))])

    unittest.main()
