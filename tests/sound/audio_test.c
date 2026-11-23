/* Regression checks against the production shared-listener mixers. */
#include <assert.h>
#include <stdarg.h>
#include "../../src/client/sound/sound.c"
#include "../../src/client/sound/sdl.c"
#ifdef USE_OPENAL
#include "../../src/client/sound/openal.c"
#endif

client_state_t cl;
client_static_t cls;
centity_t *cl_entities;
int cl_numentities;
entity_state_t cl_parse_entities[MAX_PARSE_ENTITIES];
static centity_t primary_entities[16], secondary_entities[16];
static ss_local_player_t slots[SS_MAX_LOCAL_PLAYERS];
static qboolean split_active;
static cvar_t zero = {.value = 0}, one = {.value = 1}, minus_one = {.value = -1};
static cvar_t bsp_soundpos = {.value = 0};
static cvar_t voice_volume = {.value = 1};
cvar_t *cl_paused = &zero, *cl_audiopaused = &zero;
qboolean SS_IsSessionActive(void) { return split_active; }
ss_local_player_t *SS_GetSlot(int i) { return &slots[i]; }
cvar_t *Cvar_Get(const char *name, const char *value, int flags) { (void)value; (void)flags; return !strcmp(name,"s_bsp_soundpos") ? &bsp_soundpos : &zero; }
void Com_Error(int code, const char *fmt, ...) { (void)code; (void)fmt; abort(); }
void Com_Printf(const char *fmt, ...) { (void)fmt; }
void *Z_Malloc(int size) { return calloc(1, size); }

static void TestSDLStereoCache(void)
{
	sfx_t effect = {.name = "test.wav"};
	wavinfo_t info = {
		.rate = 44100, .width = 2, .channels = 2, .samples = 8, .loopstart = 2
	};
	short data[] = {
		LittleShort(1024), LittleShort(-512),
		LittleShort(2048), LittleShort(1024),
		LittleShort(-2048), LittleShort(-1024),
		LittleShort(512), LittleShort(512)
	};
	const short expected[] = {256, 1536, -1536, 512};
	byte data8[] = {64, 128, 128, 192};
	const signed char expected8[] = {-32, 32};

	sound.speed = 44100;
	s_loadas8bit = &zero;
	assert(SDL_Cache(&effect, &info, (byte *)data, 0, 0, 0, 0, 0));
	assert(effect.cache->length == 4 && effect.cache->loopstart == 2);
	assert(effect.cache->width == 2 && effect.cache->stereo == 0);
	assert(!memcmp(effect.cache->data, expected, sizeof(expected)));
	free(effect.cache);

	sound.speed = 22050;
	s_loadas8bit = &one;
	assert(SDL_Cache(&effect, &info, (byte *)data, 0, 0, 0, 0, 0));
	assert(effect.cache->length == 2 && effect.cache->loopstart == 1);
	assert(effect.cache->width == 1 && effect.cache->stereo == 0);
	assert(((signed char *)effect.cache->data)[0] == 1);
	assert(((signed char *)effect.cache->data)[1] == -6);
	free(effect.cache);

	sound.speed = 44100;
	s_loadas8bit = &zero;
	info.width = 1;
	info.samples = 4;
	info.loopstart = -1;
	assert(SDL_Cache(&effect, &info, data8, 0, 0, 0, 0, 0));
	assert(effect.cache->length == 2 && effect.cache->loopstart == -1);
	assert(effect.cache->width == 1 && effect.cache->stereo == 0);
	assert(!memcmp(effect.cache->data, expected8, sizeof(expected8)));
	free(effect.cache);
}

static void TestSDLVoiceVolume(void)
{
	sfx_t effect = {0}, voice = {.is_voice = true};
	wavinfo_t info = {.rate = 44100, .width = 2, .channels = 1, .samples = 1, .loopstart = -1};
	short sample = LittleShort(32767);
	channel_t ch = {.leftvol = 255, .rightvol = 255, .sfx = &voice};

	s_voice_volume = &voice_volume;
	sound.speed = 44100;
	s_loadas8bit = &zero;
	assert(SDL_Cache(&voice, &info, (byte *)&sample, 0, 0, 0, 0, 0));
	snd_vol = 0;
	voice_volume.value = 2.0f;
	snd_voice_vol = (int)(S_VoiceVolume() * 256);
	memset(paintbuffer, 0, sizeof(paintbuffer));
	SDL_PaintChannelFrom16(&ch, voice.cache, 1, 0);
	assert(paintbuffer[0].left == 32767 * 510 && paintbuffer[0].right == 32767 * 510);
	ch.sfx = &effect;
	ch.pos = 0;
	SDL_PaintChannelFrom16(&ch, voice.cache, 1, 0);
	assert(paintbuffer[0].left == 32767 * 510);
	free(voice.cache);

	info.width = 1;
	byte sample8 = 192; /* Stored as signed 64 by SDL_Cache. */
	assert(SDL_Cache(&voice, &info, &sample8, 0, 0, 0, 0, 0));
	SDL_BuildScaletable(snd_scaletable, 0.5f);
	voice_volume.value = 0.0f;
	SDL_BuildScaletable(snd_voice_scaletable, S_VoiceVolume());
	ch.sfx = &voice;
	ch.pos = 0;
	memset(paintbuffer, 0, sizeof(paintbuffer));
	SDL_PaintChannelFrom8(&ch, voice.cache, 1, 0);
	assert(paintbuffer[0].left == 0 && ch.pos == 1);
	ch.sfx = &effect;
	ch.pos = 0;
	SDL_PaintChannelFrom8(&ch, voice.cache, 1, 0);
	assert(paintbuffer[0].left == 64 * 248 * 128);
	free(voice.cache);
}

#ifdef USE_OPENAL
static vec3_t al_position;
static int al_relative;
static float al_gain;
static void Source3f(ALuint source, ALenum param, ALfloat x, ALfloat y, ALfloat z)
{
	(void)source;
	if (param == AL_POSITION) { al_position[0]=x; al_position[1]=y; al_position[2]=z; }
}
static void Sourcei(ALuint source, ALenum param, ALint value)
{
	(void)source;
	if (param == AL_SOURCE_RELATIVE) al_relative=value;
}
static void Sourcef(ALuint source, ALenum param, ALfloat value)
{
	(void)source;
	if (param == AL_GAIN) { al_gain = value; }
}
static void Source3i(ALuint source, ALenum param, ALint a, ALint b, ALint c) { (void)source; (void)param; (void)a; (void)b; (void)c; }
static void SourceStop(ALuint source) { (void)source; }
trace_t CM_BoxTrace(const vec3_t a, const vec3_t b, const vec3_t c, const vec3_t d, int h, int m)
{
	trace_t trace = {.fraction=1}; (void)a; (void)b; (void)c; (void)d; (void)h; (void)m; return trace;
}
int CM_PointContents(vec3_t point, int headnode) { (void)point; (void)headnode; return 0; }
#endif

static void Reset(void)
{
	memset(&cl,0,sizeof(cl)); memset(&cls,0,sizeof(cls));
	memset(primary_entities,0,sizeof(primary_entities));
	memset(secondary_entities,0,sizeof(secondary_entities));
	memset(slots,0,sizeof(slots)); memset(channels,0,sizeof(channels));
	memset(cl_parse_entities,0,sizeof(cl_parse_entities));
	memset(s_listeners,0,sizeof(s_listeners));
	cl_entities=primary_entities; cl_numentities=16;
	cl.playernum=0; cl.servercount=7; cl.frame.valid=true; cl.frame.serverframe=10;
	cl.sound_prepped=true; cls.state=ca_active; sound.channels=2;
	s_numlisteners=1; s_numchannels=4; s_ambient=&one;
	s_listeners[0].forward[0]=1; s_listeners[0].right[1]=1; s_listeners[0].up[2]=1;
	split_active=false; paintedtime=0; sound_started=SS_SDL;
	bsp_soundpos.value=0;
#ifdef USE_OPENAL
	s_doppler=s_occlusion_strength=&zero; s_reverb_preset=&minus_one;
	qalSource3f=Source3f; qalSourcei=Sourcei; qalSourcef=Sourcef;
	qalSource3i=Source3i; qalSourceStop=SourceStop;
#endif
}

static void Split(void)
{
	split_active=true;
	slots[1].active=true; slots[1].state=SS_SLOT_ACTIVE;
	slots[1].connection_state=ca_active; slots[1].snapshot_valid=true;
	slots[1].frame.valid=true; slots[1].frame.serverframe=11;
	slots[1].servercount=cl.servercount; slots[1].playernum=1;
	slots[1].entities=secondary_entities; slots[1].entity_count=16;
	s_numlisteners=2; s_listeners[1]=s_listeners[0];
	s_listeners[1].origin[0]=5000;
}

static void TestOneShots(void)
{
	channel_t ch = {.entnum=1,.master_vol=200,.dist_mult=0.001f};
	Reset(); SDL_Spatialize(&ch); assert(ch.leftvol==200 && ch.rightvol==200);
	Split(); ch.entnum=2; SDL_Spatialize(&ch);
	assert(ch.leftvol==200 && ch.rightvol==200);
	ch.entnum=-1; SDL_Spatialize(&ch); assert(ch.leftvol==200 && ch.rightvol==200);
	ch.entnum=8; ch.fixed_origin=true; ch.origin[0]=5000; ch.origin[1]=50;
	SDL_Spatialize(&ch); assert(ch.leftvol==0 && ch.rightvol==200);
	/* Reversing player two's view must reverse its stereo direction. */
	s_listeners[1].right[1]=-1; SDL_Spatialize(&ch);
	assert(ch.leftvol==200 && ch.rightvol==0);
	/* Co-located cameras do not amplify a world sound by player count. */
	s_listeners[1]=s_listeners[0]; ch.origin[0]=0; ch.origin[1]=0;
	SDL_Spatialize(&ch); assert(ch.leftvol==100 && ch.rightvol==100);
	s_numlisteners=1; SDL_Spatialize(&ch); assert(ch.leftvol==100 && ch.rightvol==100);
}

static void TestEntitiesAndPriority(void)
{
	vec3_t origin;
	Reset(); Split();
	primary_entities[8].serverframe=10; primary_entities[8].lerp_origin[0]=20;
	secondary_entities[8].serverframe=11; secondary_entities[8].lerp_origin[0]=5000;
	GetEntitySoundOrigin(8,listener_origin,origin); assert(origin[0]==5000);
	slots[1].servercount=6; GetEntitySoundOrigin(8,listener_origin,origin); assert(origin[0]==20);
	slots[1].servercount=7; slots[1].state=SS_SLOT_DROPPED;
	GetEntitySoundOrigin(8,listener_origin,origin); assert(origin[0]==20);
	slots[1].state=SS_SLOT_ACTIVE;
	channels[0].sfx=(sfx_t *)1; channels[0].entnum=2; channels[0].end=0;
	channels[1].end=100; channels[2].end=200; channels[3].end=300;
	assert(S_PickChannel(8,0)==&channels[1]);
	assert(channels[0].sfx && channels[0].entnum==2);
}

static void TestLoops(void)
{
	entity_state_t *list[MAX_LOOP_SOUNDS];
	static sfxcache_t cache;
	static sfx_t effect;
	int count;
	Reset(); Split(); cache.length=100; effect.cache=&cache; cl.sound_precache[1]=&effect;
	cl.frame.num_entities=1;
	cl_parse_entities[0]=(entity_state_t){.number=8,.sound=1};
	slots[1].frame.num_entities=2;
	slots[1].parse_entities[0]=(entity_state_t){.number=8,.sound=1,.origin={5000,0,0}};
	slots[1].parse_entities[1]=(entity_state_t){.number=9,.sound=1,.origin={5000,50,0}};
	count=S_BuildSoundList(list,MAX_LOOP_SOUNDS); assert(count==2);
	assert(list[0]==&slots[1].parse_entities[0]);
	SDL_AddLoopSounds(); assert(channels[0].sfx==&effect && channels[0].autosound);
	assert(channels[0].leftvol==127 && channels[0].rightvol==255);
	assert(!channels[1].sfx); /* Same entity/source is not repeated per listener. */
	slots[1].parse_entities[0].sound=0;
	count=S_BuildSoundList(list,MAX_LOOP_SOUNDS); assert(count==1 && list[0]->number==9);
	s_ambient=&(cvar_t){.value=3};
	slots[1].parse_entities[1].number=2;
	count=S_BuildSoundList(list,MAX_LOOP_SOUNDS); assert(count==1 && list[0]->number==2);
}

static void TestBrushOrigin(void)
{
	static cmodel_t model;
	vec3_t origin;
	Reset(); Split(); bsp_soundpos.value=2;
	model.mins[0]=1000; model.maxs[0]=5000;
	model.mins[1]=model.mins[2]=model.maxs[1]=model.maxs[2]=0;
	cl.model_clip[1]=&model;
	primary_entities[8].current.modelindex=1;
	S_GetSpatializedOrigin(8,NULL,origin);
	assert(origin[0]==5000); /* Guest touches far surface; host is 1000 away. */
	s_numlisteners=1; S_GetSpatializedOrigin(8,NULL,origin); assert(origin[0]==1000);
}

#ifdef USE_OPENAL
static void TestOpenAL(void)
{
	sfx_t effect = {0};
	channel_t ch={.sfx=&effect,.entnum=8,.fixed_origin=true,.origin={5000,50,0},.dist_mult=0.001f,.oal_vol=1};
	Reset(); Split();
	VectorCopy(s_listeners[0].origin,listener_origin);
	VectorCopy(s_listeners[0].forward,listener_forward);
	VectorCopy(s_listeners[0].right,listener_right);
	VectorCopy(s_listeners[0].up,listener_up);
	AL_Spatialize(&ch); assert(al_relative==AL_FALSE);
	assert(al_position[0]==-50 && al_position[1]==0 && al_position[2]==0);
	s_listeners[1].right[1]=-1; AL_Spatialize(&ch); assert(al_position[0]==50);
	ch.entnum=2; AL_Spatialize(&ch); assert(al_relative==AL_TRUE);
	assert(al_position[0]==0 && al_position[1]==0 && al_position[2]==0);
}

static void TestOpenALVoiceVolume(void)
{
	sfx_t voice = {.is_voice = true}, effect = {0};
	channel_t ch = {.sfx = &voice, .oal_vol = 1.0f};

	Reset();
	s_voice_volume = &voice_volume;
	al_voice_gain_limit = S_MAX_VOICE_VOLUME;
	voice_volume.value = 1.5f;
	AL_Spatialize(&ch);
	assert(al_gain == 1.5f && al_relative == AL_TRUE);
	voice_volume.value = 0.0f;
	AL_Spatialize(&ch);
	assert(al_gain == 0.0f);
	ch.sfx = &effect;
	ch.oal_vol = 0.7f;
	AL_Spatialize(&ch);
	assert(al_gain == 0.7f);

	ch.sfx = &voice;
	ch.oal_vol = 1.0f;
	al_voice_gain_limit = 1.0f;
	voice_volume.value = 2.0f;
	AL_Spatialize(&ch);
	assert(al_gain == 1.0f);
}
#endif

int main(void)
{
	Swap_Init();
	TestSDLStereoCache();
	TestSDLVoiceVolume();
	TestOneShots(); TestEntitiesAndPriority(); TestLoops(); TestBrushOrigin();
#ifdef USE_OPENAL
	TestOpenAL();
	TestOpenALVoiceVolume();
#endif
	puts("Shared-listener audio regressions passed");
	return 0;
}
