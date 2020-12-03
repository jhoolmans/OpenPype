import json
import opentimelineio as otio
from . import lib

TRACK_TYPES = {
    "video": otio.schema.TrackKind.Video,
    "audio": otio.schema.TrackKind.Audio
}


def create_otio_rational_time(frame, fps):
    return otio.opentime.RationalTime(
        float(frame),
        float(fps)
    )


def create_otio_time_range(start_frame, frame_duration, fps):
    return otio.opentime.TimeRange(
        start_time=create_otio_rational_time(start_frame, fps),
        duration=create_otio_rational_time(frame_duration, fps)
    )


def create_otio_reference(media_pool_item):
    path = media_pool_item.GetClipProperty(
        "File Path").get("File Path")
    reformat_path = lib.get_reformated_path(path, padded=False)
    frame_start = int(media_pool_item.GetClipProperty(
        "Start").get("Start"))
    frame_duration = int(media_pool_item.GetClipProperty(
        "Frames").get("Frames"))
    fps = media_pool_item.GetClipProperty("FPS").get("FPS")

    return otio.schema.ExternalReference(
        target_url=reformat_path,
        available_range=create_otio_time_range(
            frame_start,
            frame_duration,
            fps
        )
    )


def create_otio_markers(track_item, frame_rate):
    track_item_markers = track_item.GetMarkers()
    markers = []
    for marker_frame in track_item_markers:
        note = track_item_markers[marker_frame]["note"]
        if "{" in note and "}" in note:
            metadata = json.loads(note)
        else:
            metadata = {"note": note}
        markers.append(
            otio.schema.Marker(
                name=track_item_markers[marker_frame]["name"],
                marked_range=create_otio_time_range(
                    marker_frame,
                    track_item_markers[marker_frame]["duration"],
                    frame_rate
                ),
                color=track_item_markers[marker_frame]["color"].upper(),
                metadata=metadata
            )
        )
    return markers


def create_otio_clip(track_item):
    media_pool_item = track_item.GetMediaPoolItem()
    frame_rate = media_pool_item.GetClipProperty("FPS").get("FPS")
    name = lib.get_reformated_path(track_item.GetName())
    clip = otio.schema.Clip(
        name=name,
        source_range=create_otio_time_range(
            int(track_item.GetLeftOffset()),
            int(track_item.GetDuration()),
            frame_rate
        ),
        media_reference=create_otio_reference(media_pool_item)
    )
    for marker in create_otio_markers(track_item, frame_rate):
        clip.markers.append(marker)
    return clip


def create_otio_gap(gap_start, clip_start, tl_start_frame, frame_rate):
    return otio.schema.Gap(
        source_range=create_otio_time_range(
            gap_start,
            (clip_start - tl_start_frame) - gap_start,
            frame_rate
        )
    )


def create_otio_timeline(timeline, fps):
    start_time = create_otio_rational_time(
        timeline.GetStartFrame(), fps)
    otio_timeline = otio.schema.Timeline(
        name=timeline.GetName(),
        global_start_time=start_time
    )
    return otio_timeline


def create_otio_track(track_type, track_name):
    return otio.schema.Track(
        name=track_name,
        kind=TRACK_TYPES[track_type]
    )


def get_otio_complete_timeline(project):
    # get current timeline
    timeline = project.GetCurrentTimeline()
    fps = project.GetSetting("timelineFrameRate")

    # convert timeline to otio
    otio_timeline = create_otio_timeline(timeline, fps)

    # loop all defined track types
    for track_type in list(TRACK_TYPES.keys()):
        # get total track count
        track_count = timeline.GetTrackCount(track_type)

        # loop all tracks by track indexes
        for track_index in range(1, int(track_count) + 1):
            # get current track name
            track_name = timeline.GetTrackName(track_type, track_index)

            # convert track to otio
            otio_track = create_otio_track(
                track_type, "{}{}".format(track_name, track_index))

            # get all track items in current track
            current_track_items = timeline.GetItemListInTrack(
                track_type, track_index)

            # loop available track items in current track items
            for track_item in current_track_items:
                # skip offline track items
                if track_item.GetMediaPoolItem() is None:
                    continue

                # calculate real clip start
                clip_start = track_item.GetStart() - timeline.GetStartFrame()

                # if gap between track start and clip start
                if clip_start > otio_track.available_range().duration.value:
                    # create gap and add it to track
                    otio_track.append(
                        create_otio_gap(
                            otio_track.available_range().duration.value,
                            track_item.GetStart(),
                            timeline.GetStartFrame(),
                            project.GetSetting("timelineFrameRate")
                        )
                    )

                # create otio clip and add it to track
                otio_track.append(create_otio_clip(track_item))

            # add track to otio timeline
            otio_timeline.tracks.append(otio_track)


def get_otio_clip_instance_data(track_item_data):
    """
    Return otio objects for timeline, track and clip

    Args:
        track_item_data (dict): track_item_data from list returned by
                                resolve.get_current_track_items()

    Returns:
        dict: otio clip with parent objects

    """

    track_item = track_item_data["clip"]["item"]
    project = track_item_data["project"]
    timeline = track_item_data["sequence"]
    track_type = track_item_data["track"]["type"]
    track_name = track_item_data["track"]["name"]
    track_index = track_item_data["track"]["index"]

    timeline_start = timeline.GetStartFrame()
    frame_start = track_item.GetStart()
    frame_duration = track_item.GetDuration()
    project_fps = project.GetSetting("timelineFrameRate")

    otio_clip_range = create_otio_time_range(
        frame_start, frame_duration, project_fps)
    # convert timeline to otio
    otio_timeline = create_otio_timeline(timeline, project_fps)
    # convert track to otio
    otio_track = create_otio_track(
        track_type, "{}{}".format(track_name, track_index))

    # add gap if track item is not starting from timeline start
    # if gap between track start and clip start
    if frame_start > timeline_start:
        # create gap and add it to track
        otio_track.append(
            create_otio_gap(
                0,
                frame_start,
                timeline_start,
                project_fps
            )
        )

    # create otio clip
    otio_clip = create_otio_clip(track_item)

    # add it to track
    otio_track.append(otio_clip)

    # add track to otio timeline
    otio_timeline.tracks.append(otio_track)

    return {
        "otioTimeline": otio_timeline,
        "otioTrack": otio_track,
        "otioClip": otio_clip,
        "otioClipRange": otio_clip_range
    }


def save_otio(otio_timeline, path):
    otio.adapters.write_to_file(otio_timeline, path)
