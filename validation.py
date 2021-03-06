#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2016 CNRS

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# AUTHORS
# Hervé BREDIN - http://herve.niderb.fr


from __future__ import division
from __future__ import print_function
import pandas as pd
import numpy as np
import string


class Validation(object):
    """

    Parameters
    ----------
    shots : str, optional
        Path to list of test shots. When provided, submission should only
        provide labels for these very shots.
    videos : str, optional
        Path to list of videos. When provided, evidence should only be coming
        from these very videos.
    """

    def __init__(self, shots=None, videos=None):
        super(Validation, self).__init__()
        self.shots = shots
        if self.shots:
            self.shots_ = self._load_shots(self.shots)
        self.videos = videos
        if self.videos:
            self.videos_ = self._load_videos(self.videos)

    def _load_shots(self, path):
        names = ['corpus_id', 'video_id', 'shot_id', 'start_time', 'end_time']
        dtype = {'corpus_id': str, 'video_id': str, 'shot_id': str}
        shots = pd.read_table(path, delim_whitespace=True,
                              header=None, names=names, dtype=dtype)
        shots = set((c, v, s) for _, (c, v, s, _, _) in shots.iterrows())
        return shots

    def _load_videos(self, path):
        names = ['corpus_id', 'video_id']
        dtype = {'corpus_id': str, 'video_id': str}
        videos = pd.read_table(path, delim_whitespace=True,
                               header=None, names=names, dtype=dtype)
        videos = set((c, v) for _, (c, v) in videos.iterrows())
        return videos

    def _load_submission(self, fp):

        names = ['corpus_id', 'video_id', 'shot_id',
                 'person_name', 'confidence']
        dtype = {'corpus_id': str, 'video_id': str, 'shot_id': str,
                 'person_name': str, 'confidence': np.float32}

        try:
            submission = pd.read_table(fp, delim_whitespace=True,
                                       header=None, names=names,
                                       dtype=dtype)
        except Exception as e:
            # TODO
            raise e

        return submission

    def _load_evidence(self, fp):

        names = ['person_name',
                 'corpus_id', 'video_id',
                 'modality', 'timestamp']
        dtype = {'person_name': str,
                 'corpus_id': str, 'video_id': str,
                 'modality': str, 'timestamp': np.float32}

        try:
            evidence = pd.read_table(fp, delim_whitespace=True,
                                     header=None, names=names,
                                     dtype=dtype)
        except Exception as e:
            # TODO
            raise e

        return evidence

    ALLOWED_CHARACTERS = set(string.ascii_lowercase + '_')

    def __submission_person_names(self, submission):

        person_names = set(submission['person_name'].unique())
        for person_name in person_names:
            if not set(person_name).issubset(self.ALLOWED_CHARACTERS):
                MESSAGE = 'Invalid person name ({person_name})'
                raise ValueError(MESSAGE.format(person_name=person_name))
        return True

    def __submission_shots(self, submission):

        shots = set((c, v, s) for _, (c, v, s, _, _) in submission.iterrows())

        invalid_shots = shots - self.shots_
        if invalid_shots:
            c, v, s = invalid_shots.pop()
            MESSAGE = 'Invalid shot ({corpus_id} {video_id} {shot_id})'
            message = MESSAGE.format(corpus_id=c, video_id=v, shot_id=s)
            raise ValueError(message)

        return True

    def __submission_confidence(self, submission):
        confidence = submission['confidence']

        not_finite = np.where(~np.isfinite(confidence))[0]
        if len(not_finite):
            MESSAGE = 'Incorrect confidence in submission at line {line:d}'
            raise ValueError(MESSAGE.format(line=not_finite[0]+1))

        return True

    def __evidence_videos(self, evidence):
        videos = set((c, v) for _, (_, c, v, _, _) in evidence.iterrows())
        invalid_videos = videos - self.videos_
        if invalid_videos:
            c, v = invalid_videos.pop()
            MESSAGE = 'Invalid video ({corpus_id} {video_id}) in evidence.'
            message = MESSAGE.format(corpus_id=c, video_id=v)
            raise ValueError(message)

        return True

    def __evidence_person_names(self, submission, evidence):

        duplicated = evidence.duplicated('person_name')
        if any(duplicated):
            person_name = set(evidence[duplicated]['person_name']).pop()
            MESSAGE = 'Duplicate person name in evidence ({person_name})'
            raise ValueError(MESSAGE.format(person_name=person_name))

        submission_person_names = set(submission['person_name'].unique())
        evidence_person_names = set(evidence['person_name'].unique())

        extra = evidence_person_names - submission_person_names
        if extra:
            person_name = extra.pop()
            MESSAGE = 'Extra person name in evidence ({person_name})'
            raise ValueError(MESSAGE.format(person_name=person_name))

        missing = submission_person_names - evidence_person_names
        if missing:
            person_name = missing.pop()
            MESSAGE = 'Missing person name in evidence ({person_name})'
            raise ValueError(MESSAGE.format(person_name=person_name))

        return True

    def __evidence_modalities(self, evidence):
        modalities = set(evidence['modality'].unique())
        if not modalities.issubset({'written', 'pronounced'}):
            modality = (modalities - {'written', 'pronounced'}).pop()
            MESSAGE = 'Incorrect modality in evidence ({modality})'
            raise ValueError(MESSAGE.format(modality=modality))

    def __evidence_timestamps(self, evidence):
        timestamps = evidence['timestamp']

        not_finite = np.where(~np.isfinite(timestamps))[0]
        if len(not_finite):
            MESSAGE = 'Incorrect timestamp in evidence at line {line:d}'
            raise ValueError(MESSAGE.format(line=not_finite[0]+1))

        negative = np.where(timestamps < 0.)[0]
        if len(negative):
            MESSAGE = 'Negative timestamp in evidence at line {line:d}'
            raise ValueError(MESSAGE.format(line=negative[0]+1))

        return True

    def __call__(self, fp_submission, fp_evidence=None):

        try:
            submission = self._load_submission(fp_submission)
        except ValueError as e:
            raise e

        # validate person names
        self.__submission_person_names(submission)

        # validate shots
        if self.shots:
            self.__submission_shots(submission)

        # validate confidence
        self.__submission_confidence(submission)

        if fp_evidence:

            try:
                evidence = self._load_evidence(fp_evidence)
            except ValueError as e:
                raise e

            # validate videos
            if self.videos:
                self.__evidence_videos(evidence)

            # validate timestamps
            self.__evidence_timestamps(evidence)

            # validate evidence person names
            self.__evidence_person_names(submission, evidence)

            # validate evidence modality
            self.__evidence_modalities(evidence)

        return True
