from PIL import Image

IMG_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".gif"}
DATE_FIELDS = [
    "DateTimeOriginal",
    "CreateDate",
    "ModifyDate",
    "MetadataDate",
    "FileCreationDateTime",
    "FileModificationDateTime",
    "FileAccessDateTime",
]
CAMERA_FIELDS = ["Model", "CameraModelName", "Make"]

CLIP_SCENES = {
    "close-up photo of a person":"portrait", 
    "photo of one or more animals":"animals",
    "photo of people playing sports":"sports",
    "digital or hand-made drawing":"drawing",
    "computer or smartphone screenshot":"screenshot",
    "document with written text":"text",
    "photo of one or more objects":"objects",
    "selfie":"selfie",
    "group photo":"group",
    "photo of a landscape":"landscape",
    "photo of an architectural work":"landscape",
    "photo of a city or town":"landscape",
    "photo of a natural scene":"landscape",
    "photo of the interior of a building":"interior",
    "photo of a piece of art":"art",
    "photo of a music show":"concert",
    "food or drink photo":"food",
    "funny meme image":"meme",
    "photo of one or more vehicles":"cars",
    "image without anything remarkable":"default"
}

PIL_ORIENTATION_LUT = {
    "Rotate 90 CW" : Image.Transpose.ROTATE_270,
    "Rotate 270 CW": Image.Transpose.ROTATE_90,
    "Rotate 180": Image.Transpose.ROTATE_180
}

FACE_DET_THRESHOLD = 0.55 # 0.7

