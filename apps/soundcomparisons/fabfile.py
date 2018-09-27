import os
import pathlib
from tempfile import NamedTemporaryFile
import gzip
import re
import json
from itertools import groupby
from collections import Counter

from fabric.api import sudo, get
from fabric.contrib.files import exists
from fabtools import require
from appconfig.tasks import *

init()


def sql(app, sql_):
    """
    Run some SQL remotely on the app's database
    """
    sudo("""mysql -e "{0}" -D {1}""".format(sql_.replace('\n', ' '), app.name))


def read_from_db(app, sql_):
    """
    - Run some SQL remotely on the app's database, which writes results to OUTFILE.
    - Transfer the resulting file to the local machine.
    - Return the result rows as list of lists.
    """
    remote_path = "/tmp/query.txt"
    if exists(remote_path):
        sudo('rm {0}'.format(remote_path))
    sql(app, sql_.replace('OUTFILE', "OUTFILE '{0}'".format(remote_path)))
    sudo('gzip -f {0}'.format(remote_path))
    local_file = NamedTemporaryFile(delete=False, suffix='.gz')
    get(remote_path + '.gz', local_file.name)
    sudo('rm {0}.gz'.format(remote_path))
    with gzip.open(local_file.name, mode='rt', encoding='utf8') as fp:
        res = [l.replace('\n', '').split('\t') for l in fp.readlines()]
    os.remove(local_file.name)
    return res


@task_app_from_environment
def shutdown(app):
    sudo('systemctl stop php7.0-fpm.service')
    upload_db_to_cdstar(app, dbname='v4')


@task_app_from_environment
def backup_to_cdstar(app):
    upload_db_to_cdstar(app, dbname='v4')


#
# SQL query retrieving information to map soundfiles to existing Transcriptions.
#
TRANSCRIPTIONS = """\
select distinct
  l.FilePathPart, 
  w.SoundFileWordIdentifierText, 
  t.LanguageIx, 
  t.IxElicitation, 
  t.IxMorphologicalInstance, 
  t.AlternativePhoneticRealisationIx, 
  t.AlternativeLexemIx 
into 
  OUTFILE
from 
  Transcriptions as t, Languages as l, Words as w 
where 
  l.LanguageIx = t.LanguageIx 
  and t.IxElicitation = w.IxElicitation 
  and t.IxMorphologicalInstance = w.IxMorphologicalInstance 
order by 
  l.FilePathPart;
"""

LANGUAGES = """\
select
    FilePathPart, LanguageIx 
into 
  OUTFILE
from Languages;
"""

WORDS = """\
select
    SoundFileWordIdentifierText, IxElicitation, IxMorphologicalInstance
into 
  OUTFILE
from Words;
"""

@task_app_from_environment
def load_contributorimages_catalog(app, catalog):
    """
    load available contributor and speaker images into the db
    Usage:
    fab load_contributorimages_catalog:production,/path/to/soundcomparisons-data/imagefiles/catalog.json

    :param catalog: Path to imagesfiles/catalog.json in a clone of the repos clld/soundcomparisons-data
    """
    with pathlib.Path(catalog).open() as fp:
        cat = json.load(fp)

    table = NamedTemporaryFile(suffix='.gz', delete=False)
    with gzip.open(table.name, mode='wt', encoding='utf8') as tbl:
        for oid, data in cat.items():
            md = data['metadata']
            if(md['name']):
                tag = md['name']
                fpp = ''
                # if tag represents a FilePathPart_\d+ (speaker image[s])
                # remove trailing indices and fill column 'filepathpart' with FilePathPart only
                arr = re.split(r'_\d+$', tag)
                if len(arr) == 2:
                    fpp = arr[0]
                tbl.write('\t'.join([
                    tag,
                    fpp,
                    'https://cdstar.shh.mpg.de/bitstreams/{0}/{1}'.format(
                        oid, md['path'])]) + '\n')

    remote_path = '/tmp/contributorimages.txt.gz'
    require.files.file(path=remote_path, source=table.name, use_sudo=True, mode='644')
    os.remove(table.name)
    sudo('gunzip -f {0}'.format(remote_path))
    remote_path = remote_path[:-3]

    tsql = """\
CREATE OR REPLACE TABLE soundcomparisons.contributorimages (
  tag varchar(255) NOT NULL,
  filepathpart varchar(255) DEFAULT '',
  url TEXT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;"""
    sql(app, tsql)
    sudo('mysqlimport {0} {1}'.format(app.name, remote_path))

    sudo('rm {0}'.format(remote_path))

    sudo('systemctl restart php7.0-fpm.service')


@task_app_from_environment
def load_soundfile_catalog(app, catalog):
    """
    load available soundfiles into the db
    Usage:
    fab load_soundfile_catalog:production,/path/to/soundcomparisons-data/soundfiles/catalog.json

    :param catalog: Path to soundfiles/catalog.json in a clone of the repos clld/soundcomparisons-data
    """
    with pathlib.Path(catalog).open() as fp:
        cat = json.load(fp)

    # Restructure catalog into {"stem":["uid", [".EXT1", ".EXT2", ...]]}
    catalog = {}
    for (k, v) in cat.items():
        stem = v['metadata']['name']
        fmts = [pathlib.Path(bs['bitstreamid']).suffix for bs in v['bitstreams']]
        catalog[stem] = [k, fmts]
    del cat

    # We keep track of soundfiles for existing Transcriptions by deleting the corresponding catalog
    # keys from this set:
    ckeys = set(catalog.keys())

    def urls_from_catalog(stem):
        oid, fmts = catalog[stem]
        return [
            'https://cdstar.shh.mpg.de/bitstreams/{0}/{1}{2}'.format(
                oid, stem, fmt) for fmt in list(set(fmts) & set(['.mp3','.ogg']))]

    transcriptions = read_from_db(app, TRANSCRIPTIONS)

    def transcription_grouper(row):
        """
        Transcriptions are identified uniquely by the 5-tuple
        - LanguageIx,
        - IxElicitation,
        - IxMorphologicalInstance,
        - AlternativePhoneticRealisationIx,
        - AlternativeLexemIx

        Associated soundfiles OTOH are identified by FilePathPart and SoundFileWordIdentifierText
        which may vary across Transcriptions for the same (Language, Word).
        """
        return tuple(row[2:])

    def write_row(tbl, ixl, ixe, ixm, pron, lex, urls):
        if urls:
            tbl.write('\t'.join([ixl, ixe, ixm, str(pron), str(lex), json.dumps(urls)]) + '\n')

    table = NamedTemporaryFile(suffix='.gz', delete=False)
    with gzip.open(table.name, mode='wt', encoding='utf8') as tbl:
        for key, tts in groupby(
                sorted(transcriptions, key=transcription_grouper), transcription_grouper):
            LanguageIx, IxElicitation, IxMorphologicalInstance, pron, lex = key
            pron, lex = int(pron), int(lex)
            suffix = ''
            if lex > 1:
                suffix += '_lex{0}'.format(lex)
            if pron > 1:
                suffix += '_pron{0}'.format(pron)
            urls = []
            for tt in tts:
                stem = tt[0] + tt[1] + suffix
                if stem in catalog:
                    if stem in ckeys:
                        ckeys.remove(stem)
                    urls.extend(urls_from_catalog(stem))
            write_row(tbl, LanguageIx, IxElicitation, IxMorphologicalInstance, pron, lex, urls)

        #
        # To be able to assign soundfiles to dummy transcriptions, we need to map soundfile names
        # to LanguageIx, IxElicitation, IxMorphologicalInstance.
        #
        languages = {r[0]: r[1] for r in read_from_db(app, LANGUAGES)}
        # We sort the FilePathPart by descending length, to prevent matching short prefixes.
        lkeys = sorted(languages, key=lambda w: len(w), reverse=True)
        words = {r[0]: r[1:] for r in read_from_db(app, WORDS)}
        # We sort the SoundFileWordIdentifierText by descending length, to prevent matching
        # short prefixes.
        sfwits = sorted(words, key=lambda w: len(w), reverse=True)

        uwords = Counter()
        rems = Counter()
        lex_pattern = re.compile('_lex(?P<n>[0-9])$')
        pron_pattern = re.compile('_pron(?P<n>[0-9])$')
        for key in sorted(ckeys):  # Loop over soundfiles which haven't been assigned yet.
            for fpp in lkeys:
                if key.startswith(fpp):
                    sfwit = key[len(fpp):]
                    break
            else:  # No matching FilePathPart was found!
                continue

            for word in sfwits:
                if sfwit.startswith(word):
                    sfwit = word
                    break
            else:  # No matching SoundFileWordIdentifierText was found!
                uwords.update([sfwit])
                continue

            lex, pron = 0, 0  # Default for dummy transcriptions.
            rem = key[len(fpp) + len(sfwit):]
            if rem:  # Check unmatched suffixes of the soundfile stem.
                m = lex_pattern.match(rem)
                if m:
                    lex = int(m.group('n'))
                m = pron_pattern.match(rem)
                if m:
                    pron = int(m.group('n'))
                if not (lex or pron):
                    rems.update([rem])
                    continue  # The suffix didn't match the lex or pron pattern.

            ixe, ixm = words[sfwit]
            write_row(tbl, languages[fpp], ixe, ixm, pron, lex, urls_from_catalog(key))

    remote_path = '/tmp/soundfiles.txt.gz'
    require.files.file(path=remote_path, source=table.name, use_sudo=True, mode='644')
    os.remove(table.name)
    sudo('gunzip -f {0}'.format(remote_path))
    remote_path = remote_path[:-3]

    tsql = """\
CREATE OR REPLACE TABLE soundcomparisons.soundfiles (
  LanguageIx bigint(20) unsigned NOT NULL,
  IxElicitation int(10) unsigned NOT NULL,
  IxMorphologicalInstance tinyint(3) unsigned NOT NULL,
  AlternativePhoneticRealisationIx tinyint(3) unsigned,
  AlternativeLexemIx tinyint(3) unsigned,
  urls TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8;"""
    sql(app, tsql)
    sudo('mysqlimport {0} {1}'.format(app.name, remote_path))

    sudo('rm {0}'.format(remote_path))

    #print('unknown words referenced in soundfiles ({0}):'.format(sum(uwords.values())))
    #print(uwords)
    #print('suffixes ({0}):'.format(sum(rems.values())))
    #print(rems)
    sudo('systemctl restart php7.0-fpm.service')
