# Copyright (C) 2026  Tomáš Sourada, Katia Vendrame, Jan Hajič, jr.
#
# This file is part of the MusICA MetaBench source code, licensed under
# the GNU General Public License v3.0 or later (SPDX: GPL-3.0-or-later).
# See the LICENSE-SOURCE-CODE file in the repository root for the full
# license text, or <https://www.gnu.org/licenses/>.

"""
Methods for automatic extraction of ground truth answers and pools of distractors for the benchmark questions.
Each meta-question in the benchmark should be associated with a function in this file that implements the logic for
extracting the ground truth answer and distractor pool from the symbolic score of a piece (or some other way). The generate_benchmark.py
script will dynamically load this file and call the appropriate function for each question-piece pair to populate the
benchmark with ground truth answers and distractors.
"""

# TODO: in future, instead of random sampling of distractors, you can create prob distribution of samples over dataset and sample from that.
from operator import index

from music21 import converter, note, chord, stream, interval, pitch, meter,key,roman,duration
import os
from utils import get_musicxml_file_path
import yaml
import itertools
import re

def get_tonal_intervals():

    perfect_numbers = [1,4,5,8]
    major_numbers = [2,3,6,7]

    ontology = {}

    # perfect-type intervals
    for n in perfect_numbers:
        for q in ["P","A","d"]:
            name = f"{q}{n}"
            try:
                iv = interval.Interval(name)
                #possible also to use iv.niceName or iv.name, but simpleName is more concise and still recognizable
                ontology[name] = iv.niceName
            except:
                pass

    # major/minor-type intervals
    for n in major_numbers:
        for q in ["M","m","A","d"]:
            name = f"{q}{n}"
            try:
                iv = interval.Interval(name)
                ontology[name] = iv.niceName
            except:
                pass

    return ontology
   
def get_tonal_notes():
    notes = {}
    for pc in range(12):
        p = pitch.Pitch()
        p.pitchClass = pc
        enh_name = p.getEnharmonic().name
        for note_name in [p.name, enh_name]:
            if "#" in note_name:
                if '##' in note_name:
                    notes[note_name] = note_name[0]+" double sharp"
                else:
                    notes[note_name] = note_name[0]+" sharp"
            elif "-" in note_name:
                if '--' in note_name:
                    notes[note_name] = note_name[0]+" double flat"
                else:
                    notes[note_name] = note_name[0]+" flat"
            else:
                notes[note_name] = note_name[0]
    
    return notes

def get_rhythm():
    # We iterate through the official music21 duration types
    # to map their standard quarterLength to their name.
    rhythm_dict = {}

    # duration.typeToDuration maps type names to quarter lengths
    for duration_type, quarter_length in duration.typeToDuration.items():
        if quarter_length > 0:
            rhythm_dict[str(quarter_length)] = duration_type
            # Add single-dotted variant (quarter length * 1.5)
            dotted_ql = quarter_length * 1.5
            rhythm_dict[str(dotted_ql)] = f"dotted-{duration_type}"

    # Add tuplets (common ratios)
    tuplet_names = {
        "2/3": "triplet",
        "3/2": "duplet",
        "4/3": "quadruplet",
        "5/4": "quintuplet",
        "6/4": "sextuplet",
        "7/4": "septuplet",
        "8/7": "octuplet",
    }
    for ratio, name in tuplet_names.items():
        rhythm_dict[ratio] = name

    return rhythm_dict

def get_time_signatures():
    """
    Returns a dictionary of common real-world time signatures.
    """
    # Sample common real time signatures
    common_time_signatures = [
        "2/4", "3/4", "4/4", "5/4", "6/4",
        "3/8", "6/8", "9/8", "12/8",
        "2/2", "3/2", "4/2",
        "5/8", "7/8", "11/8"
    ]

    ontology = {ts: ts for ts in common_time_signatures}
    return ontology

def get_tonality():
    modes = ['major', 'minor']  #, 'dorian', 'phrygian', 'lydian', 'mixolydian', 'locrian']
    ontology = {}
    for pc in range(12):
        p = pitch.Pitch()
        p.pitchClass = pc
        
        # Get both the primary name and its enharmonic equivalent
        pitch_names = {p.name}
        enharmonic = p.getEnharmonic()
        if enharmonic and enharmonic.name != p.name:
            pitch_names.add(enharmonic.name)
        
        # Add both tonality and mode combinations for all enharmonic spellings
        for pitch_name in pitch_names:
            for mode in modes:
                word = f"{pitch_name} {mode}"
                ontology[word] = word
    
    return ontology

def get_ordinal_suffix(n: int) -> str:
      
    if 11 <= (n % 100) <= 13:
        return 'th'
    else:
        last_digit = n % 10
        if last_digit == 1:
            return 'st'
        elif last_digit == 2:
            return 'nd'
        elif last_digit == 3:
            return 'rd'
        else:
            return 'th'


class VirtualIndexList:
    """
    A list-like class that does not store data, but generates values on-the-fly.
    
    This class mimics the behavior of a standard Python list by implementing 
    the __getitem__ magic method. Instead of retrieving data from internal 
    storage, it invokes get_nice_target_index(target_index) for every access.
    """

    def __init__(self, size: int):
        self._size = size

    def __getitem__(self, index: int) -> str:
        """
        Allows indexing (e.g., obj[5]) and slicing (e.g., obj[1:3]).
        """
        if isinstance(index, slice):
            return [self.get_nice_target_index(i) for i in range(*index.indices(self._size))]
        
        # Handle negative indexing
        if index < 0:
            index += self._size
            
        return self.get_nice_target_index(index)

    def __len__(self):
        """Returns the virtual size of the list."""
        return self._size

    def get_nice_target_index(self, target_index: int) -> str:

        # # Retrieve the dictionary for the target index
        # target_index_dicts = self.ontology['target_index']
        # for target_index_dict in target_index_dicts:
        #     if str(target_index) in target_index_dict:
        #         return target_index_dict[str(target_index)]

        # Fallback to generating the ordinal suffix dynamically
        return {f"{target_index}":f"{str(target_index+1)+ get_ordinal_suffix(target_index+1)}"}
       
    def __iter__(self):
        """Allows the instance to be used in loops or iterables."""
        for i in range(self._size):
            yield self.get_nice_target_index(i)
        # Always yield "last" as a special index representing the last note, 
        # regardless of the size of the list
        yield {"end": "last"}
    
def get_chords():
    pitch_classes = list(range(12))  # 0–11
    ontology = set()
    max_notes = 4 #number of voices
    for r in range(2, max_notes + 1):  # dyads → tetrads
        for pcs in itertools.combinations(pitch_classes, r):

            # build chord from pitch classes
            pitches = [pitch.Pitch(midi=60 + pc) for pc in pcs]
            ch = chord.Chord(pitches)
            name = ch.commonName
            if "with" in name:  # filter out chords with added tones (e.g., "C major with added sixth")
                name = name.split(" with")[0]
                
            if name:  # filter None / empty
                ontology.add(name)
  
    ontology = {chord_name: chord_name for chord_name in ontology}
    return ontology


def get_cadence_types():
    """
    Loads or builds cadence types ontology.
    - If selected_cadences.yaml exists, loads it
    - Otherwise builds the base list, adds defaults, and saves to file
    - Always ensures the file is saved for persistence
    """
    ontology_path = "selected_cadences.yaml"

    # Try to load existing file
    if os.path.exists(ontology_path):
        with open(ontology_path, 'r') as file:
            print(f"Loading cadence types ontology from {ontology_path}")
            ontology = yaml.load(file, Loader=yaml.FullLoader)
            if ontology:
                return ontology

    # Build base cadences if file doesn't exist or is empty
    print(f"Building cadence types ontology...")
    selected_list = [
        "V - I", "V7 - I", "v - i", "V - i", "V7 - i", 
        "vii - I", "vii7 - I", "vii - i", "vii7 - i",
        "IV - I", "iv - I", "IV - i", "iv - i",
        "I - V", "i - V", "IV - V", "iv - V", "ii - V", "ii - V", 
        "vi - V", "VI - V", "ii7 - V", "ii7 - V",
        "V - vi", "V - VI", "V7 - vi", "V7 - VI",
        "vi - ii", "VI - ii", "IV - ii", "iv - ii", 
        "I - vi", "i - VI", "iii - vi", "III - VI",
        "ii - IV", "ii - iv", "I - IV", "i - iv",
        "V - IV", "V - iv", "ii - V7", "ii - V7",
        "iii - IV", "III - IV"
    ]
    items_to_add = []
    for _k in selected_list:
        first_chord = _k.split(" - ")[0]
        items_to_add.append(f"{first_chord} - f{first_chord}")

    selected_list += items_to_add
    selected_list = set(selected_list)
    selected_list = list(selected_list)
    ontology = {cad: cad for cad in selected_list}
    
    # Save the base ontology to file for future use
    with open(ontology_path, 'w') as file:
        yaml.dump(ontology, file)
        print(f"Cadence types ontology saved to {ontology_path}")

    return ontology

def get_cadences():
    pitch_classes = list(range(12))  # 0–11
    ontology = set()
    max_notes = 3 #number of voices
    
    for r in range(3, max_notes + 1):  # dyads → tetrads
        for pcs in itertools.combinations(pitch_classes, r):

            # build chord from pitch classes
            pitches = [pitch.Pitch(midi=60 + pc) for pc in pcs]
            ch = chord.Chord(pitches)
            for pcs2 in itertools.combinations(pitch_classes, r):
                # Use cached pitches
                pitches2 = [pitch.Pitch(midi=60 + pc) for pc in pcs2]
                ch2 = chord.Chord(pitches2)

                # Generate Roman numeral figures
                rn = str(roman.romanNumeralFromChord(ch, key.Key('A')).figure)
                rn2 = str(roman.romanNumeralFromChord(ch2, key.Key('A')).figure)

                if rn != rn2:
                    cad_name = f"{rn}: {rn2}"
                    ontology.add(cad_name)
    
    ontology = {cad_name: cad_name for cad_name in ontology}
    return ontology


def get_rhythm_props():
    # Define the rhythmic proportions to consider
    rhythmic_proportions = [0.5, 1.0, 2.0, 3.0, 0.25, 0.33, 4.0, 6.0]  # e.g., half, equal, double
    ontology = {str(prop) : (f"1:{round(prop)}") for prop in rhythmic_proportions if prop >=1}

    ontology.update({str(prop) : (f"{str(round(1/prop))}:1") for prop in rhythmic_proportions if prop < 1})
    ontology.update({'0.67': "2:3"})
    ontology.update({'1.5': "3:2"})
    # ontology = {0:""}
    return ontology
# def get_harmonic_cadences():
    
class AnswerDistractorExtractors:
    def __init__(self, config_yaml):
        self.config = config_yaml
        self.rng = self.config['rng']

        # print(self.config)
        music_config = self.config['music_ontology_settings']
        if "harmonic_system" in self.config:
            system = self.config["harmonic_system"]
        else:
            system = "tonal"
        self.ontology = yaml.load(open(music_config['ontology_path'],'r'), Loader=yaml.FullLoader)
        if "interval" in self.ontology.keys():
            self.dict_interval_ontology = {k: v for d in self.ontology['interval'] for k, v in d.items()}
        else:
            self.dict_interval_ontology = self.build_interval_ontology(system)
            self.ontology['interval'] = [{k:v} for k,v in self.dict_interval_ontology.items()]

        if "pitch" in self.ontology.keys():
            self.dict_note_ontology = {k: v for d in self.ontology['pitch'] for k, v in d.items()}
            
        else:
            self.dict_note_ontology = self.build_note_ontology(system)
            self.ontology['pitch'] = [{k:v} for k,v in self.dict_note_ontology.items()]

        if "rhythm" in self.ontology.keys():
            self.dict_rhythm_ontology = {k: v for d in self.ontology['rhythm'] for k, v in d.items()}
        else:
            self.dict_rhythm_ontology = self.build_rhythm_ontology(system)
            self.ontology['rhythm'] = [{k:v} for k,v in self.dict_rhythm_ontology.items()]

        if "time_signature" in self.ontology.keys():
            self.dict_time_signature_ontology = {k: v for d in self.ontology['time_signature'] for k, v in d.items()}
        else:
            self.dict_time_signature_ontology = self.build_time_signature_ontology(system)
            self.ontology['time_signature'] = [{k:v} for k,v in self.dict_time_signature_ontology.items()]
        
        if "tonality" in self.ontology.keys():
            self.dict_tonality_ontology = {k: v for d in self.ontology['tonality'] for k, v in d.items()}
        else:
            self.dict_tonality_ontology = self.build_tonality_ontology(system)
            self.ontology['tonality'] = [{k:v} for k,v in self.dict_tonality_ontology.items()]
        
        if "chords" in self.ontology.keys():
            self.dict_chord_ontology = {k: v for d in self.ontology['chords'] for k, v in d.items()}
        else:
            self.dict_chord_ontology = self.build_chord_ontology(system)
            self.ontology['chords'] = [{k:v} for k,v in self.dict_chord_ontology.items()]

        if "rhythm_proportion" in self.ontology.keys():
            self.dict_rhythm_prop_ontology = {k: v for d in self.ontology['rhythm_proportion'] for k, v in d.items()}
        else:
            self.dict_rhythm_prop_ontology = self.build_rhythm_prop_ontology(system)
            self.ontology['rhythm_proportion'] = [{k:v} for k,v in self.dict_rhythm_prop_ontology.items()]

        self.use_xml_part_names = music_config.get('use_xml_part_names', False)
        if "voice" in self.ontology.keys() and not(self.use_xml_part_names):
            self.voice_mapping = {}
            idx = 0
            temp_dict = {k: v for d in self.ontology['voice'] for k, v in d.items()}
            for short_name, full_name in temp_dict.items():
                self.voice_mapping[short_name] = idx
                idx +=1
            self.use_xml_part_names = False
            
        if "cadences" in self.ontology.keys():
            self.dict_cadence_ontology = {k: v for d in self.ontology['cadences'] for k, v in d.items()}
        #  TODO: TO SOLVE / very slow
        else:
            self.dict_cadence_ontology = self.build_cadence_ontology(system)
            self.ontology['cadences'] = [{k:v} for k,v in self.dict_cadence_ontology.items()]
        self.distractor_pool_size = self.config.get('distractor_pool_size', 4)

        if self.ontology.get('target_index') is None or self.config.get('use_all_inds', None):
            self.use_all_inds = True
            
            # Use a virtual index that behaves like a list of (let's say) 30 indices, 
            # but generates the nice string representation on the fly when accessed,
            # for any index (never returns IndexError).
            # This is beneficial, because we do not know in advance the length of the pieces.
            # We use 30 as a reasonable default
            self.ontology['target_index'] = VirtualIndexList(self.config.get('max_target_index', 200))
            #self.ontology['target_index'] = [get_nice_target_index(self, idx) for idx in range(self.distractor_pool_size*100)]
            
        else:
            self.use_all_inds = False 
        
        self.min_num_distractors = self.config['min_num_distractors']
        self.random_distractors = self.config.get('random_distractors', False)
        self.verbose = self.config.get('verbose', False)
      #  yaml.dump(self.ontology, open('generated_ontology.yaml','w'))

        # Added a predefined pools of random distractors.
        # Those will be used:
        # (1) when insufficient number of distractors is generated from the piece,
        # to achieve the desired number of distractors (Tomas will implement)
        # (2) when use_random_distractors is true, distractors may be sampled from 
        # those pools on a single line of code, probably in the function `extract_answer_and_distractors`.
        # The pools are not identical to those generated by the individual functions for all the functions.
        self.random_distractor_pools = self.build_random_distractor_pools()

    def build_random_distractor_pools(self):
        # Pre-build random distractor pools for each ontology category

        dummy_quantity_pool = range(self.distractor_pool_size)

        random_distractor_pools = {
            "get_harmonic_tonality": list(self.dict_tonality_ontology.values()),
            "get_nth_note": list(self.dict_note_ontology.values()),
            # a dummy value as predefined potential number of occurences of a note
            "get_note_quantity": dummy_quantity_pool,
            "get_nth_interval": list(self.dict_interval_ontology.values()),
            "get_interval_quantity": dummy_quantity_pool,
            "get_nth_rhythm": list(self.dict_rhythm_ontology.values()),
            "get_time_signature": list(self.dict_time_signature_ontology.values()),
            "get_rhythm_pattern": list(self.dict_rhythm_prop_ontology.values()),
            "get_harmonic_chord": list(self.dict_chord_ontology.values()),
            "get_harmonic_cadence": list(self.dict_cadence_ontology.values()),
            "get_rhythm_pattern_count" : dummy_quantity_pool,
            "get_rhythm_count": dummy_quantity_pool,
        }
        return random_distractor_pools


    def build_cadence_ontology(self, system):
        if system=="tonal":
            
            return get_cadence_types()
                # "V-I": "authentic cadence",
                # "V-vi": "deceptive cadence",
                # "IV-I": "plagal cadence",
                # "V-VI": "half cadence",
                # "I-V": "retrograde authentic cadence",

                # Add more cadences as needed
            
        else:
            raise ValueError(f"Unknown hamonic system for harmonical recognition: {system}")

    def build_rhythm_prop_ontology(self, system):
        if system=="tonal":
            return get_rhythm_props()
        else:
            raise ValueError(f"Unknown hamonic system for harmonical recognition: {system}")

    def build_chord_ontology(self, system):
        if system=="tonal":
            return get_chords()

        else:
            raise ValueError(f"Unknown hamonic system for harmonical recognition: {system}")

    def build_tonality_ontology(self, system):
        if system=="tonal":
            return get_tonality()
        else:
            raise ValueError(f"Unknown hamonic system for harmonical recognition: {system}")
        
    def build_rhythm_ontology(self, system):
        if system=="tonal":
            return get_rhythm()

        else:
            raise ValueError(f"Unknown hamonic system for harmonical recognition: {system}")
    
    def build_interval_ontology(self,system):

        if system=="tonal":
            return get_tonal_intervals()

        else:
            raise ValueError(f"Unknown hamonic system for harmonical recognition: {system}")
    def build_note_ontology(self, system):
        if system=="tonal":
            return get_tonal_notes()

        else:
            raise ValueError(f"Unknown hamonic system for harmonical recognition: {system}")
    def build_time_signature_ontology(self, system):
        if system=="tonal":
            return get_time_signatures()

        else:
            raise ValueError(f"Unknown hamonic system for harmonical recognition: {system}")
    def get_part_and_notes(self, score, values, rests=False):
        if self.use_xml_part_names:
            score_voices = {str(i):score.parts[i].partName for i in range(len(score.parts))}
            stop_it = 0
            notes = []
            while not notes:
                chosen_voice = self.rng.choice(list(score_voices.keys()))
                part_index = int(chosen_voice)
                voice_key = score_voices[chosen_voice]
                values['voice'] = voice_key
                target_part = score.parts[part_index]
                # Flatten the part (to remove measure hierarchies) and extract only the notes (ignoring rests/chords)
                if rests:
                    notes = list(target_part.flatten().notesAndRests)
                else:
                    notes = list(target_part.flatten().getElementsByClass(note.Note))
                stop_it +=1
                if not notes and stop_it >= len(score_voices):
                    if self.verbose:
                        print(f"Warning: No valid notes found in any part of the score. Skipping datapoint: {score.title}.")
                    return None, None, values
            
        else: # default, for same n-voices setup on all data, defined in ontology['voice']
            voice_key = values.get('voice')
            if voice_key not in self.voice_mapping:
                raise ValueError(f"Invalid voice specified: {voice_key}. Expected one of {self.ontology['voice']}.")
            part_index = self.voice_mapping[voice_key]
            # Check if the score has the expected number of parts
            if part_index >= len(score.parts):
                raise IndexError(f"The parsed score does not contain a part for voice '{voice_key}'.")
            target_part = score.parts[part_index]
            # Flatten the part (to remove measure hierarchies) and extract only the notes (ignoring rests/chords)
            notes = list(target_part.flatten().getElementsByClass(note.Note))
            if not notes:
                raise ValueError(f"No valid notes found in part '{voice_key}' for the score '{score.title}'.")  
        return notes, values
    
    def get_nth_note(self, path: str, question_values: dict) -> str:
        """
        Logic: Parses a MusicXML file and returns the scientific pitch notation 
        of the index-th note in the specified voice part.
        
        Args:
            path (str): The path to the directory of the piece, which contains the MusicXML file.
            values (dict): A dictionary containing the value for {index} and {voice}, e.g., {"target_index": 1, "voice": "Soprano"}
            
        Returns:
            str: return NOTE NAME ONLY (e.g., "G", "E flat").
        """
            # Get the path to the MusicXML file
        musicxml_path = get_musicxml_file_path(path)

        if not os.path.exists(musicxml_path):
            raise FileNotFoundError(f"Could not find file: {musicxml_path}")
        
        # Parse the MusicXML file into a music21 Stream
        score = converter.parse(musicxml_path)
        notes, question_values = self.get_part_and_notes(score, question_values)     
            
        if self.use_all_inds:
            note_index = int(self.rng.choice(range(len(notes)-1)))
            question_values['target_index'] = str(note_index) #self.ontology["target_index"][int(note_index)]
        else:
            note_index = question_values.get('target_index')
            if note_index == 'end':
                    note_index = -1
            else:
                note_index = self.ontology['target_index'][note_index]
            # Check if the target_index is out of bounds
            if note_index >= len(notes) - 1:
                raise IndexError("Interval target_index out of range")
        # Get the target note and return its scientific pitch notation
        target_note = notes[note_index]
        
        if not(self.random_distractors):
            # Build a set of candidate distractor notes (exclude the true note)
            for idx in range(len(score.parts)):
                other_part = score.parts[idx]
                other_notes = list(other_part.flatten().getElementsByClass(note.Note))
                notes += other_notes
            possible_distractors = set([n.name for n in notes if n.name != target_note.name])
            possible_distractors = list(possible_distractors)
            distractor_pool = [self.dict_note_ontology[sample] for sample in possible_distractors]
        else:
            distractor_pool = []
        
        return self.dict_note_ontology[target_note.name], distractor_pool, question_values

    
    def get_note_quantity(self, path: str, question_values: dict) -> tuple[str, list[str]]:
        """
            meta-question_id: 0
            meta-question: Which voice part has the {quantity} number of {pitch} notes in the provided excerpt?
            
            Logic: Parses a MusicXML file and returns the voice part that has the most/least number of notes of a given pitch.
            
            Args:
                path (str): The path to the directory of the piece, which contains the MusicXML file.
                values (dict): A dictionary containing the value for {quantity} and {pitch}, e.g., {"quantity": "most", "pitch": "G"}
                
            Returns:
                str: The voice part with the most/least number of the specified pitch (e.g., "Soprano").
                list[str]: A list of distractor voice parts with ground truth excluded.
        """
        # Get the path to the MusicXML file
        musicxml_path = get_musicxml_file_path(path)

        if not os.path.exists(musicxml_path):
            raise FileNotFoundError(f"Could not find file: {musicxml_path}")
        
        # Parse the MusicXML file into a music21 Stream
        score = converter.parse(musicxml_path)
        target_pitch = question_values.get('pitch')

        if target_pitch not in self.dict_note_ontology.keys():
            raise ValueError(f"Invalid pitch specified: {target_pitch}. Expected one of {self.dict_note_ontology}.")

        notes, question_values = self.get_part_and_notes(score, question_values)
        # Count occurrences of the target pitch in the selected part
        count = int(sum(1 for n in notes if n.name == target_pitch))

        if not self.random_distractors:
            all_notes = []
            for idx in range(len(score.parts)):
                other_part = score.parts[idx]
                other_notes = list(other_part.flatten().getElementsByClass(note.Note))
                all_notes.append([n.name for n in other_notes])
            possible_values = []
            for line in all_notes:
                for _n in list(set(line)):
                    possible_values.append(int(sum(1 for n in line if n == _n)))
            possible_values = list(set(possible_values))
            possible_values = [c for c in possible_values if c != count]
            distractor_pool = possible_values
        else:
            distractor_pool = []

        return count, distractor_pool, question_values
    

    def get_nth_interval(self, path: str, question_values: dict) -> tuple[str, list[str]]:
        """
            meta-question_id: 0
            meta-question: What is the {target_index} {voice} interval in the provided excerpt?
            
            Logic: Parses a MusicXML file and returns the specified interval in the specified voice part.
            
            Args:
                path (str): The path to the directory of the piece, which contains the MusicXML file.
                values (dict): A dictionary containing the value for {target_index} and {voice}, e.g., {"target_index": 1, "voice": "S"}
                
            Returns:
                str: The specified interval (e.g., "major third").
                list[str]: A list of distractor intervals with ground truth excluded.
        """
        musicxml_path = get_musicxml_file_path(path)

        if not os.path.exists(musicxml_path):
            raise FileNotFoundError(f"Could not find file: {musicxml_path}")
        
        # Parse the MusicXML file into a music21 Stream
        score = converter.parse(musicxml_path)
                
        notes, question_values = self.get_part_and_notes(score, question_values)

        if self.use_all_inds:
            note_index = int(self.rng.choice(range(len(notes)-1)))
            question_values['target_index'] = str(note_index)
        else:
            note_index = question_values.get('target_index')
            
            if note_index == 'end':
                note_index = -1
            else:
                note_index = self.ontology['target_index'][note_index]
            # Check if the target_index is out of bounds
            if note_index >= len(notes) - 1:
                raise IndexError("Interval target_index out of range")

        n1 = notes[note_index]
        n2 = notes[note_index + 1]
        iv = interval.Interval(n1, n2)
        target_interval_name = iv.simpleName
        
        if not self.random_distractors:
            all_interval_keys = []
            for idx in range(len(score.parts)):
                other_part = score.parts[idx]
                other_notes = list(other_part.flatten().getElementsByClass(note.Note))
                for note_idx in range(len(other_notes)-1):
                    n1 = other_notes[note_idx]
                    n2 = other_notes[note_idx + 1]
                    iv = interval.Interval(n1, n2)
                    interval_name = iv.simpleName
                    all_interval_keys.append(interval_name)
            possible_values = list(set(all_interval_keys))
            possible_values = [iv for iv in possible_values if iv != target_interval_name]
            distractor_pool = [self.dict_interval_ontology[sample] for sample in possible_values]
        else:
            distractor_pool = []

        return self.dict_interval_ontology[target_interval_name], distractor_pool, question_values


    def get_interval_quantity(self, path: str, question_values: dict) -> tuple[str, list[str]]:
        """
            meta-question_id: 0
            meta-question: Which voice part has the {quantity} number of {interval} intervals in the provided excerpt?
            
            Logic: Parses a MusicXML file and returns the voice part that has the most/least number of intervals of a given type.
            
            Args:
                path (str): The path to the directory of the piece, which contains the MusicXML file.
                values (dict): A dictionary containing the value for {quantity} and {interval}, e.g., {"quantity": "most", "interval": "major third"}
                
            Returns:
                str: The voice part with the most/least number of the specified interval (e.g., "Soprano").
                list[str]: A list of distractor voice parts with ground truth excluded.
        """
        # breakpoint()
                # Get the path to the MusicXML file
        musicxml_path = get_musicxml_file_path(path)

        if not os.path.exists(musicxml_path):
            raise FileNotFoundError(f"Could not find file: {musicxml_path}")
        
        # Parse the MusicXML file into a music21 Stream
        score = converter.parse(musicxml_path)
        target_interval = question_values.get('interval')
       
        if target_interval not in self.dict_interval_ontology.keys():
            raise ValueError(f"Invalid pitch specified: {target_interval}. Expected one of {self.dict_interval_ontology}.")

        notes, question_values = self.get_part_and_notes(score, question_values)          
    
        #for test_note in score.parts[0].flatten().getElementsByClass(note.Note):
        intervals = []
        for note_idx in range(len(notes)-1):
            n1 = notes[note_idx]
            n2 = notes[note_idx + 1]
            iv = interval.Interval(n1, n2)
            interval_name = iv.simpleName
            intervals.append(interval_name)

        count = int(sum(1 for n in intervals if n == target_interval))
        
        if not self.random_distractors:
            voice_intervals = []
            for idx in range(len(score.parts)):
                other_part = score.parts[idx]
                other_notes = list(other_part.flatten().getElementsByClass(note.Note))
                for note_idx in range(len(other_notes)-1):
                    n1 = other_notes[note_idx]
                    n2 = other_notes[note_idx + 1]
                    iv = interval.Interval(n1, n2)
                    interval_name = iv.simpleName
                    intervals.append(interval_name)
                voice_intervals.append(intervals)
            distractor_pool = []
            for line in voice_intervals:
                for nn in set(line):
                    distractor_pool.append(int(sum(1 for _ in line if _ == nn)))
            distractor_pool = list(set(distractor_pool))
            distractor_pool = [c for c in distractor_pool if c != count]
            
        else:
            distractor_pool = []

        return count, distractor_pool, question_values

    def get_nth_rhythm(self, path: str, question_values: dict) -> str:
        """
        Logic: Parses a MusicXML file and returns the rhythm (e.g., quarter, eighth) of the index-th note in the specified voice part.

        Args:
            path (str): The path to the directory of the piece, which contains the MusicXML file.
            values (dict): A dictionary containing the value for {index} and {voice}, e.g., {"target_index": 1, "voice": "S"}

        Returns:
            str: return RHYTHM ONLY (e.g., "quarter", "eighth").
        """
        # Get the path to the MusicXML file
        musicxml_path = get_musicxml_file_path(path)

        if not os.path.exists(musicxml_path):
            raise FileNotFoundError(f"Could not find file: {musicxml_path}")

        # Parse the MusicXML file into a music21 Stream
        score = converter.parse(musicxml_path)

        notes, question_values = self.get_part_and_notes(score, question_values, rests = True)
       
        if self.use_all_inds:
            note_index = int(self.rng.choice(range(len(notes)-1)))
            question_values['target_index'] = str(note_index)
        else:
            note_index = question_values.get('target_index')
            
            if note_index == 'end':
                note_index = -1
            else:
                note_index = int(note_index)
            # Check if the target_index is out of bounds
            if note_index >= len(notes) - 1:
                raise IndexError("Interval target_index out of range")

        # Get the target note and return its rhythm
        target_note = notes[note_index]
        target_rhythm = str(target_note.quarterLength)

        if not self.random_distractors:
            all_notes = []
            for idx in range(len(score.parts)):
                other_part = score.parts[idx]
                other_notes = list(other_part.flatten().notesAndRests)
                all_notes += other_notes
            # Build a set of candidate distractor rhythms (exclude the true rhythm)

            distractor_pool_set = set(n.quarterLength for n in all_notes)
            distractor_pool = [self.dict_rhythm_ontology[str(sample)] for sample in distractor_pool_set if str(sample) != target_rhythm and str(sample) in self.dict_rhythm_ontology.keys()]
            # distractor_pool = [{str(n.quarterLength): str(n.type)} for n in set_all_notes if str(n.quarterLength) != target_rhythm]
        else:
            distractor_pool = [] #self.rng.choice(list(self.dict_rhythm_ontology.values()), len(list(self.dict_rhythm_ontology.values())), replace=False).tolist()
            
        return self.dict_rhythm_ontology[target_rhythm], distractor_pool, question_values

    def get_rhythm_count(self, path: str, question_values: dict) -> str:
        """
        Logic: Parses a MusicXML file and returns the rhythm (e.g., quarter, eighth) of the index-th note in the specified voice part.

        Args:
            path (str): The path to the directory of the piece, which contains the MusicXML file.
            values (dict): A dictionary containing the value for {index} and {voice}, e.g., {"target_index": 1, "voice": "S"}

        Returns:
            str: return RHYTHM ONLY (e.g., "quarter", "eighth").
        """
        # Get the path to the MusicXML file
        musicxml_path = get_musicxml_file_path(path)

        if not os.path.exists(musicxml_path):
            raise FileNotFoundError(f"Could not find file: {musicxml_path}")

        # Parse the MusicXML file into a music21 Stream
        score = converter.parse(musicxml_path)
        notes, question_values = self.get_part_and_notes(score, question_values, rests = True)
        
        count = int(sum(1 for n in notes if str(n.quarterLength) == question_values.get('rhythm')))
    
        if not self.random_distractors:
            all_notes = []
            for idx in range(len(score.parts)):
                other_part = score.parts[idx]
                other_notes = list(other_part.flatten().notesAndRests)
                all_notes.append([n.quarterLength for n in other_notes])
            possible_values = []
            for line in all_notes:
                for _n in list(set(line)):
                    possible_values.append(int(sum(1 for n in line if n == _n)))
            possible_values = list(set(possible_values))
            possible_values = [c for c in possible_values if c != count]
            distractor_pool = possible_values
            
        else:
            distractor_pool = [] #self.rng.choice(list(self.dict_rhythm_ontology.values()), len(list(self.dict_rhythm_ontology.values())), replace=False).tolist()
            
        return count, distractor_pool, question_values

    def get_rhythm_pattern(self, path: str, question_values: dict) -> tuple[str, list[str]]:
        
        musicxml_path = get_musicxml_file_path(path)
        score = converter.parse(musicxml_path)
        notes, question_values = self.get_part_and_notes(score, question_values, rests = True)
       
        if self.use_all_inds:
            note_index = int(self.rng.choice(range(len(notes)-1)))
            question_values['target_index'] = str(note_index) #self.ontology['target_index'][note_index]
        else:
            note_index = question_values.get('target_index')

            if note_index == 'end':
                note_index = -1
            # Check if the target_index is out of bounds
            note_index = int(note_index)
            if note_index >= len(notes) or int(note_index) < -len(notes):
                raise IndexError(f"Requested note target_index '{note_index}' is out of bounds. The part has {len(notes)} notes.")

        # Parse the MusicXML file into a music21 Stream
        
        props = []
        for note_idx in range(len(notes)-1):
            n1 = notes[note_idx].quarterLength
            n2 = notes[note_idx + 1].quarterLength
            if n1 and n2 != 0:
                rhythmic_proportion = n2/n1
    
            # rhythmic_proportion = n2/n1 if n1 != 0 else 0
            # iv = interval.Interval(n1, n2)
            # interval_name = iv.simpleName
            # intervals.append(interval_name)
            props.append(str(round(rhythmic_proportion, 2)))

        target_prop = float(props[note_index])
        try:
            target_prop_name = self.dict_rhythm_prop_ontology[str(target_prop)]
        except KeyError:
            if target_prop >= 1:
                self.dict_rhythm_prop_ontology[str(round(target_prop,2))] =f"1:{round(target_prop)}"
            else:
                self.dict_rhythm_prop_ontology[str(round(target_prop,2))] = f"{str(round(1/target_prop))}:1"
            if self.config.get('verbose', False):
                print(f"Could not match detected rhythm prop '{target_prop}' to any ontology entry. Added pattern {self.dict_rhythm_prop_ontology[str(round(target_prop,2))]} to ontology.")
              
        if not self.random_distractors:
            all_props = []
            for idx in range(len(score.parts)):
                other_part = score.parts[idx]
                other_notes = list(other_part.flatten().notesAndRests)
                for note_idx in range(len(other_notes)-1):
                    n1 = other_notes[note_idx].quarterLength
                    n2 = other_notes[note_idx + 1].quarterLength
                    if n1 and n2 != 0:
                        rhythmic_proporton= n2/n1
                    all_props.append(rhythmic_proporton)
            all_props_names = []
            for _p in all_props:
                #_key = str(round(_p,2))
                try:
                    new_el = self.dict_rhythm_prop_ontology[str(round(_p,2))]
                except KeyError:
                    if _p >= 1:
                        self.dict_rhythm_prop_ontology[str(round(_p,2))] =f"1:{round(_p)}"
                    else:
                        self.dict_rhythm_prop_ontology[str(round(_p,2))] = f"{str(round(1/_p))}:1"
                    if self.config.get('verbose', False):
                        print(f"Could not match detected rhythm prop '{_p}' to any ontology entry. Added pattern {self.dict_rhythm_prop_ontology[str(round(_p,2))]} to ontology.")
                        
                all_props_names.append(self.dict_rhythm_prop_ontology[str(round(_p,2))])
                
            distractor_pool = set(all_props_names)
            distractor_pool.discard(target_prop_name)
            distractor_pool = list(distractor_pool)
        else:
            distractor_pool = []

        return target_prop_name, distractor_pool, question_values
    
    def get_rhythm_pattern_count(self, path: str, question_values: dict) -> tuple[str, list[str]]:
        musicxml_path = get_musicxml_file_path(path)
        if not os.path.exists(musicxml_path):
            raise FileNotFoundError(f"Could not find file: {musicxml_path}")
        score = converter.parse(musicxml_path)
        # # target_rhythm = question_values.get('rhythm')
       
        # if target_rhythm not in self.dict_rhythm_ontology.keys():
        #     raise ValueError(f"Invalid rhythm specified: {target_rhythm}. Expected one of {self.dict_rhythm_ontology}.")
        
        notes, question_values = self.get_part_and_notes(score, question_values, rests = True)

        props = []
        for note_idx in range(len(notes)-1):
            n1 = notes[note_idx].quarterLength
            n2 = notes[note_idx + 1].quarterLength
            if n1 and n2 != 0:
                rhythmic_proportion = n2/n1
    
            props.append(str(round(rhythmic_proportion, 2)))
    
        target_pattern = question_values.get('rhythm_proportion')
        # go through ontology and find the corresponding key for the target_pattern value
        
        count = int(sum(1 for n in props if n == target_pattern))
            
        if not self.random_distractors:
            all_props = []
            for idx in range(len(score.parts)):
                other_part = score.parts[idx]
                other_notes = list(other_part.flatten().notesAndRests)
                for note_idx in range(len(other_notes)-1):
                    n1 = other_notes[note_idx].quarterLength
                    n2 = other_notes[note_idx + 1].quarterLength
                    tmp = []
                    if n1 and n2 != 0:
                        rhythmic_proporton= n2/n1
                        tmp.append(str(round(rhythmic_proporton, 2)))
                    all_props.append(tmp)
            possible_values = []
            for line in all_props:
                for _n in list(set(line)):
                    possible_values.append(int(sum(1 for n in line if n == _n)))
            possible_values = list(set(possible_values))
            possible_values = [c for c in possible_values if c != count]
            distractor_pool = possible_values

        else:
            distractor_pool = []

        return count, distractor_pool, question_values

    def get_time_signature(self, path: str, question_values: dict) -> tuple[str, list[str]]:
        musicxml_path = get_musicxml_file_path(path)

        if not os.path.exists(musicxml_path):
            raise FileNotFoundError(f"Could not find file: {musicxml_path}")
        
        # Parse the MusicXML file into a music21 Stream
        score = converter.parse(musicxml_path)
        time_signatures = score.recurse().getElementsByClass('TimeSignature')
        
        if not time_signatures:
            if self.config.get('verbose', False):
                print("No time signatures found in the piece., skipping question.")
            
            return None, distractor_pool, question_values
        else:
            target_time_signature = time_signatures[0].ratioString
            target_time_signature = self.dict_time_signature_ontology[target_time_signature]
            distractor_pool = list(self.dict_time_signature_ontology.values())

            return target_time_signature, distractor_pool, question_values

    def get_harmonic_tonality(self, path: str, question_values: dict) -> tuple[str, list[str]]:
        musicxml_path = get_musicxml_file_path(path)

        if not os.path.exists(musicxml_path):
            raise FileNotFoundError(f"Could not find file: {musicxml_path}")
        
        # Parse the MusicXML file into a music21 Stream
        score = converter.parse(musicxml_path)

        #key_signatures = score.recurse().getElementsByClass('KeySignature')
        key_signatures = score.analyze('key')
        harmonic_function = question_values["function"]
        keys_dict = {}
        
        if not key_signatures:
            if self.config.get('verbose', False):
                print("No key signatures found in the piece., skipping question. If this happens frequently, consider skipping this question (not clearly tonal dataset)")
            
            return None, [], question_values
        
        else:
            keys_dict["tonic"]  = key_signatures.name
            #keys_dict["dominant"]  = key.Key(key_signatures.getDominant().name, key_signatures.mode).asKey().name
            #keys_dict["dominant"]  = key_signatures.getDominant().name
            keys_dict["relative minor/major"] = key_signatures.relative.name                    
            target_key_signature_name = self.dict_tonality_ontology[keys_dict[harmonic_function]]            
            if not(self.random_distractors):
                possible_values = [v for k,v in keys_dict.items() if k != harmonic_function]
                distractor_pool = [self.dict_tonality_ontology[sample] for sample in possible_values]
            else:
                distractor_pool = []
            return target_key_signature_name, distractor_pool, question_values
        
    def get_harmonic_chord(self, path: str, question_values: dict) -> tuple[str, list[str]]:
        musicxml_path = get_musicxml_file_path(path)

        if not os.path.exists(musicxml_path):
            raise FileNotFoundError(f"Could not find file: {musicxml_path}")
        
        # Parse the MusicXML file into a music21 Stream
        score = converter.parse(musicxml_path)
        # chords = score.recurse().getElementsByClass('Chord')
        chords = score.chordify().recurse().getElementsByClass('Chord')
        chords = list(chords)
        
        if not chords:
            raise ValueError(f"No valid chords found.")
        if self.use_all_inds:
            note_index = int(self.rng.choice(range(len(chords)-1)))
            question_values['target_index'] = str(note_index) #self.ontology['target_index'][note_index]
        else:
            note_index = question_values.get('target_index')

        if note_index == 'end':
            note_index = -1

        # Check if the target_index is out of bounds
        if note_index >= len(chords) or int(note_index) < -len(chords):
            raise IndexError(f"Requested note target_index '{note_index}' is out of bounds. The part has {len(chords)} chords.")

        target_chord = chords[note_index].commonName
        
        if not chords:
            if self.config.get('verbose', False):
                print("No chords found in the piece., skipping question.")
            
            return None, [], question_values
        else:
            if "with" in target_chord:  # filter out chords with added tones (e.g., "C major with added sixth")
                target_chord = target_chord.split(" with")[0]
            if target_chord not in self.dict_chord_ontology.keys():
                return None, [], question_values
            else:
                target_chord_name = self.dict_chord_ontology[target_chord]
            
            if not(self.random_distractors):
                chords = [chord.commonName for chord in chords]
                chords = set(chords)

                distractor_pool = list(chords)
                distractor_pool_values = []
                for cch in distractor_pool:
                    simple_cch = cch.split(" with")[0] if "with" in cch else cch
                    if simple_cch in self.dict_chord_ontology.keys() and not simple_cch == target_chord:
                        distractor_pool_values.append(self.dict_chord_ontology[simple_cch])
                    
            else:
                distractor_pool = []         
            
            return target_chord_name, distractor_pool_values, question_values
        
    def get_harmonic_cadence(self, path: str, question_values: dict) -> tuple[str, list[str]]:
        musicxml_path = get_musicxml_file_path(path)

        if not os.path.exists(musicxml_path):
            raise FileNotFoundError(f"Could not find file: {musicxml_path}")
        
        # Parse the MusicXML file into a music21 Stream
        score = converter.parse(musicxml_path)
        # chords = score.recurse().getElementsByClass('Chord')
        chords = score.chordify().recurse().getElementsByClass('Chord')
        chords = list(chords)
        signature = score.recurse().getElementsByClass('KeySignature')

        if not chords:
            raise ValueError(f"No valid chords found.")
        if self.use_all_inds:
            note_index = int(self.rng.choice(range(len(chords)-1)))
            question_values['target_index'] = str(note_index) #self.ontology['target_index'][note_index]
        else:
            note_index = question_values.get('target_index')

        if note_index == 'end':
            note_index = -1

        # Check if the target_index is out of bounds
        if note_index >= len(chords) or int(note_index) < -len(chords):
            raise IndexError(f"Requested note target_index '{note_index}' is out of bounds. The part has {len(chords)} chords.")
        
        if not chords:
            if self.config.get('verbose', False):
                print("No chords found in the piece., skipping question.")
            
            return None, [], question_values
        else:
            # Get Roman numerals relative to a detected key
            k = score.analyze('key')
                        
            target_chord1 = chords[note_index]
            # Ensure we don't go out of bounds for the second chord
            if note_index + 1 >= len(chords):
                return None, [], question_values

            target_chord2 = chords[note_index + 1]
            
            rn1 = str(roman.romanNumeralFromChord(target_chord1, k).figure)
            rn2 = str(roman.romanNumeralFromChord(target_chord2, k).figure)
            
            target_cadence_str = f"{rn1} - {rn2}"

            target_cadence = None
            
            # 1. Exact match first
            if target_cadence_str in self.dict_cadence_ontology:
                target_cadence = self.dict_cadence_ontology[target_cadence_str]
            else:
                # 2. Try to find a match in ontology by simplifying the Roman numerals (e.g., V7 -> V)
                # We use regex to find if any key in ontology "fits" our target.
                # Specifically, if the ontology has "V - I" and we have "V7 - I", we might want to match it.
                for ont_cadence in self.dict_cadence_ontology.keys():
                    if ont_cadence == "other": continue
                    
                    # Create a regex that allows for some flexibility in the Roman numeral figures
                    # (e.g., matching 'V' with 'V7' or 'vii' with 'vii7')
                    parts = ont_cadence.split(" - ")
                    if len(parts) == 2:
                        # Escape special characters like  and build a regex that matches the base RN
                        # but allows for suffixes like '7', '65', etc.
                        p1 = re.escape(parts[0])
                        p2 = re.escape(parts[1])
                        # This regex checks if our target_cadence_str starts with the ontology pattern segments
                        pattern = f"^{p1}.* - {p2}.*$"
                        if re.match(pattern, target_cadence_str):
                            target_cadence = self.dict_cadence_ontology[ont_cadence]
                            break

            if target_cadence is None:
                
                new_rn1 = extract_roman_numerals(rn1)
                new_rn2 = extract_roman_numerals(rn2)

                # print(rn1, rn2)
                # print(new_rn1, new_rn2)
                # input("Press Enter to continue...")

                self.dict_cadence_ontology[f"{new_rn1} - {new_rn2}"] = f"{new_rn1} - {new_rn2}"
                target_cadence = f"{new_rn1} - {new_rn2}"

                if self.config.get('verbose', False):
                    print(f"Could not match detected cadence '{target_cadence_str}' to any ontology entry. Consider expanding the cadence ontology or check the parsing logic. Added pattern f\"{new_rn1} - {new_rn2}\" to ontology.")
                
                with open("selected_cadences.yaml", "w") as f:
                    yaml.dump(self.dict_cadence_ontology, f)
            
            if not(self.random_distractors):
                #TODO: very slow to generate all cadences for piece, so for now use just random distractors, because ontology for cadences is quite specific and small.
                distractor_pool = [v for k,v in self.dict_cadence_ontology.items() if v != target_cadence]
            else:
                distractor_pool = []

            return target_cadence, distractor_pool, question_values

    
    def extract_answer_and_distractors(self, method, path: str, question_values: dict) -> tuple[str, list[str]]:
        """
        A wrapper function that extracts the ground truth answer and distractor pool for a given question.
        
        Args:
            path (str): The path to the directory of the piece, which contains the MusicXML file.
            question_values (dict): A dictionary containing the values needed to extract the answer (e.g., {"target_index": 1, "voice": "S"}).
            distractor_keys (list[str]): A list of keys corresponding to distractors in the ontology.
        Returns:
            tuple[str, list[str]]: A tuple containing the ground truth answer and a list of
            distractors.
        """
        # This function can be extended to handle different types of questions by checking the question type and calling the appropriate extraction method.
        # For now, it directly calls get_nth_note as an example.
        
        musicxml_path = get_musicxml_file_path(path)
        score = converter.parse(musicxml_path)
        # if len(score.parts) != 4:
        #     if self.config.get('verbose', False):
        #         print(f"Warning: Expected 4 parts in the score, but found {len(score.parts)}. Check the MusicXML file for potential issues.")
        #     return None, [], question_values, {}
        # else:
        ground_truth, ground_truth_pool, new_values = method(path, question_values) # self.get_nth_note_ground_truth(path, question_values)
        #new values look like this 
        #{'target_index': 38, 'voice': 'S'}
        # i need: new_words = {"target_index": 38th, "voice": "soprano"}
        if ground_truth is None:
            if self.config.get('verbose', False):
                print(f"Could not extract ground truth for question {method.__name__}. This question will be skipped.")
            return None, [], question_values, {}
        
        new_words = {}
        for var_name, value_symbol in new_values.items():
            value_symbol = str(value_symbol)
            if var_name in self.ontology:
                if var_name == 'target_index':
                    new_words[var_name] = self.ontology['target_index'][int(value_symbol)][value_symbol]
                # else:
                #     possible_dicts = self.ontology[var_name]
                #     for dict_item in possible_dicts:
                #         if value_symbol in dict_item:
                #             new_words[var_name] = dict_item[value_symbol]  

        # TODO: Kacko, would the following make sense?
        # if this code is used later, the code for sampling random distractors can be removed from the individual functions.
        # if self.random_distractors:
        #     # throw away the extracted distractors from the piece and use the precomputed ones
        #     method_name = method.__name__
        #     ground_truth_pool = self.rng.choice(self.random_distractor_pools[method_name], self.distractor_pool_size, replace=False).tolist()


    # distractor_pool = self.get_distractors(distractor_keys, ground_truth_pool)
    # breakpoint()
    # additional, just safety reasons: Ensure the ground truth is not in the distractor pool
        if ground_truth in ground_truth_pool:
            ground_truth_pool.remove(ground_truth)

        if len(set(ground_truth_pool))< self.min_num_distractors:
            # Not enough distractors. We need to add additional distractors (from the pool of random distractors for the given question)
            
            method_name = method.__name__
            
            if self.config.get('verbose', False):
                print(f"Warning: Only {len(set(ground_truth_pool))} unique distractors generated for question {method_name}. Falling back to random distractors.")
            
            ground_truth_pool = list(set(ground_truth_pool))
            len_diff = self.min_num_distractors - len(ground_truth_pool)          

            random_distractor_pool = set(self.random_distractor_pools[method_name])
            
            # make sure that the pool we will be sampling from does not contain anything already present in the pool
            for distractor in ground_truth_pool:
                random_distractor_pool.discard(distractor)

            # and make sure it does not contain the ground truth
            random_distractor_pool.discard(ground_truth)

            # to ensure reproducibility
            random_distractor_pool = sorted(list(random_distractor_pool))

            additional_distractors = self.rng.choice(random_distractor_pool, len_diff, replace=False).tolist()
            
            ground_truth_pool += additional_distractors

        if len(ground_truth_pool) < self.min_num_distractors:
            if self.verbose:
                print(f"Warning: Not enough unique distractors available to reach the minimum of {self.min_num_distractors}. Only {len(set(ground_truth_pool))} unique distractors will be used.")

        ground_truth_pool = list(set(ground_truth_pool))

        # Sort the distractor pool in order to ensure reproducibility, which is hindered by the use of sets.
        ground_truth_pool = sorted(ground_truth_pool)
        self.ontology['rhythm_proportion'] = [{k:v} for k,v in self.dict_rhythm_prop_ontology.items()]
        self.ontology['cadence'] = [{k:v} for k,v in self.dict_cadence_ontology.items()]
        yaml.dump(self.ontology, open('generated_ontology.yaml','w'))
        return ground_truth, ground_truth_pool, new_values, new_words


def remove_lowercase_and_digits(text):
    # Pattern explanation:
    # [a-z0-9] matches any lowercase letter OR any digit
    pattern = r'[a-z0-9]'
    
    # re.sub(pattern, replacement, string)
    # We replace any matched character with an empty string ''
    cleaned = re.sub(pattern, '', text)
    
    return cleaned

def extract_roman_numerals(text):
    # Pattern explanation:
    # [IVXLCDM]+ matches one or more characters from the set
    # re.IGNORECASE makes it count 'i', 'v', etc. if desired
    pattern = r'[IVXLCDM]+'
    
    # findall returns a list of all matches found
    matches = re.findall(pattern, text, flags=re.IGNORECASE)
    
    return matches[0]

