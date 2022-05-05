from typing import List

from myptv.particle_matching_mod import match_blob_files, matching_using_time, initiate_time_matching


class TrackingMatcher(match_blob_files):
    '''matches blobs from several cameras into a particles using timed data'''

    def get_particles(self, frames=None):

        for cam in self.blobs:
            print(f'---------- CAM ----------')
            print(cam)
        return
        if frames is None:
            frames = self.time_lst

        self.cam_names = [cam.name for cam in self.imsys.cameras]

        # start matching, one frame at a time
        self.particles = []
        print('')


        windows = split_frames_to_windows()
        track_opts_for_all_windows = []
        for window in windows:
            opts = get_all_match_options_for_window()
            track_opts = []
            for opt in opts:
                track_opts.append(track_blobs_across_window())
                # track_opts.sort(lambda track_opt: sum_all_tracks_length(track_opt))

            track_opts_for_all_windows.append(track_opts)


        ################## Attempt II ##################

        win_size = 2
        windows = [frames[i:i+win_size] for i in range(len(frames))[::win_size]]
        for window in windows:
            for frame in window:
                print(frame)

        return
        # for index, frame in enumerate(frames):
        #     frames_window = frames[0:win_size]
        #     for f in frames_window:
        #         1. opts = get_all_match_options_for_window()
        #         2. links = get_all_links_options_for_window
        #         3. sort all match options according to length of links
        #         4. continue with all matches such that:
        #             a. each blob is only used once
        #             b. each paticle is only connected to a single paticle


class Blob:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y


class TwoDimFrame:
    def __init__(self, blobs):
        self.blobs: List[Blob] = blobs


class ThreeDimTuple:
    def __init__(self, x: float, y: float, z:float):
        self.x = x
        self.y = y
        self.z = z

    def __repr__(self):
        return f'{type(self)}: ({self.x}, {self.y}, {self.z})'


class ThreeDimPoint(ThreeDimTuple):
    pass


class ThreeDimVector(ThreeDimTuple):
    def __init__(self, x: float, y: float, z:float):
        length_before_normalization = (x**2 + y**2 + z**2)**0.5
        scaling_factor = 1/length_before_normalization
        self.x = x * scaling_factor
        self.y = y * scaling_factor
        self.z = z * scaling_factor

    def __add__(self, other):
        if isinstance(other, ThreeDimVector):
            return ThreeDimVector(
                self.x + other.x,
                self.y + other.y,
                self.y + other.y,
            )
        raise ValueError


class Ray:
    def __init__(self, origin: ThreeDimPoint, direction: ThreeDimVector):
        self.origin = origin
        self.direction = direction
