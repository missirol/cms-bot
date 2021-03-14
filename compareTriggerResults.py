#!/usr/bin/env python
"""
Script to compare the content of edm::TriggerResults collections in EDM files across multiple workflows
 - CMSSW dependencies: edmDumpEventContent, hltDiff
"""
from __future__ import print_function
import argparse
import os
import fnmatch
import subprocess

def KILL(message):
  raise RuntimeError(message)

def WARNING(message):
  print('>> Warning -- '+message)

def get_output(cmds, permissive=False):
  prc = subprocess.Popen(cmds, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  out, err = prc.communicate()
  if (not permissive) and prc.returncode:
    KILL('get_output -- shell command failed (execute command to reproduce the error):\n'+' '*14+'> '+cmd)
  return (out, err)

def command_output_lines(cmds, stdout=True, stderr=False, permissive=False):
  _tmp_out_ls = []
  if not (stdout or stderr):
    WARNING('command_output_lines -- options "stdout" and "stderr" both set to FALSE, returning empty list')
    return _tmp_out_ls

  _tmp_out = get_output(cmds, permissive=permissive)
  if stdout: _tmp_out_ls += _tmp_out[0].split('\n')
  if stderr: _tmp_out_ls += _tmp_out[1].split('\n')

  return _tmp_out_ls

def which(program, permissive=False, verbose=False):
  _exe_ls = []
  fpath, fname = os.path.split(program)
  if fpath:
    if os.path.isfile(program) and os.access(program, os.X_OK):
      _exe_ls += [program]
  else:
    for path in os.environ["PATH"].split(os.pathsep):
      path = path.strip('"')
      exe_file = os.path.join(path, program)
      if os.path.isfile(exe_file) and os.access(exe_file, os.X_OK):
        _exe_ls += [exe_file]
  _exe_ls = list(set(_exe_ls))

  if len(_exe_ls) == 0:
    log_msg = 'which -- executable not found: '+program
    if permissive:
      if verbose: WARNING(log_msg)
      return None
    else:
      KILL(log_msg)

  if verbose and len(_exe_ls) > 1:
    WARNING('which -- executable "'+program+'" has multiple matches: \n'+str(_exe_ls))

  return _exe_ls[0]

def getListOfTriggerResultsProcessNames(inputEDMFile, verbosity=0):
  ret = []
  try:
    for outl in command_output_lines(['edmDumpEventContent', inputEDMFile]):
      outl_split = [_tmp.replace('"','') for _tmp in outl.split()]
      if len(outl_split) != 4: continue
      if outl_split[0] == 'edm::TriggerResults' and outl_split[1] == 'TriggerResults' and outl_split[2] == '':
        ret.append(outl_split[3])
    ret = list(set(ret))
  except:
    if verbosity > 0:
      WARNING('getListOfTriggerResultsProcessNames -- failed to execute "edmDumpEventContent '+inputEDMFile+'" (will return empty list)')
  return ret

def compareTriggerResults(inputDir1, inputDir2, filePattern, outputDir, maxEvents, dryRun=False, verbosity=0):
  files1 = [os.path.join(dp, f) for dp, dn, filenames in os.walk(inputDir1) for f in filenames if fnmatch.fnmatch(f, filePattern)]
  files2 = [os.path.join(dp, f) for dp, dn, filenames in os.walk(inputDir2) for f in filenames if fnmatch.fnmatch(f, filePattern)]
  ret = {}
  for f1 in sorted(files1):
    fBasename, wfName = os.path.basename(f1), os.path.dirname(os.path.relpath(f1, inputDir1))
    f2 = os.path.join(inputDir2, wfName, fBasename)
    if f2 not in files2: continue

    # get list of processNames of edm::TriggerResults collections
    trProcessNames = getListOfTriggerResultsProcessNames(f1, verbosity)
    if not trProcessNames: continue

    # remove duplicates across different EDM files of the same workflow
    # (would become unnecessary calls to hltDiff)
    trProcessNames2 = trProcessNames[:]
    for _tmp1 in trProcessNames:
      if wfName in ret:
        if _tmp1 in ret[wfName]:
          trProcessNames2.remove(_tmp1)

    # skip if empty list
    if not trProcessNames2: continue

    # fill dictionary
    if wfName not in ret: ret[wfName] = {}

    for _tmp1 in trProcessNames2:
      ret[wfName][_tmp1] = [f1, f2]

  # hltDiff calls
  numWorkflowsWithDiffs = 0
  summaryLines = ['| {:25} | {:15} | {:12} | {:}'.format('Events with differences', 'Input Events', 'Process Name', 'Workflow')]
  summaryLines += ['-'*100]

  for wfName in ret:
    wfOutputDir = os.path.join(outputDir, wfName)
    try:
      if not dryRun:
        os.makedirs(wfOutputDir)
    except:
      WARNING('failed to create output directory (will skip comparisons for this workflow): '+wfOutputDir)

    wfHasDiff = False
    for procName in ret[wfName]:
      hltDiff_cmds = ['hltDiff', '-m', str(maxEvents)]
      hltDiff_cmds += ['-o', ret[wfName][procName][0], '-O', procName]
      hltDiff_cmds += ['-n', ret[wfName][procName][1], '-N', procName]
      hltDiff_cmds += ['-j', '-F', os.path.join(wfOutputDir, procName)]

      if dryRun:
        if verbosity > 0: print('> '+' '.join(hltDiff_cmds))
        continue

      hltDiff_outputs = command_output_lines(hltDiff_cmds)

      diffStats = []
      with open(os.path.join(wfOutputDir, procName+'.log'), 'w') as outputLogFile:
        for _tmp in hltDiff_outputs:
          outputLogFile.write(_tmp+'\n')
          # caveat: relies on format of hltDiff outputs to stdout
          #  - see https://github.com/cms-sw/cmssw/blob/master/HLTrigger/Tools/bin/hltDiff.cc
          if _tmp.startswith('Found '):
            diffStatsTmp = [int(s) for s in _tmp.split() if s.isdigit()]
            if len(diffStatsTmp) == 2:
              if diffStats:
                WARNING('logic error -- hltDiff statistics already known (check output of hltDiff)')
              else:
                diffStats = diffStatsTmp[:]
            else:
              WARNING('format error -- extracted N!=2 integers from output of hltDiff: '+str(diffStatsTmp))

      if not diffStats: diffStats = [0, 0]
      summaryLines += ['| {:25d} | {:15d} | {:12} | {:}'.format(diffStats[1], diffStats[0], procName, wfName)]
      wfHasDiff |= diffStats[1] > 0

    if wfHasDiff: numWorkflowsWithDiffs += 1
    summaryLines += ['-'*100]

  if dryRun: return

  with open(os.path.join(outputDir, 'summary.log'), 'w') as outputSummaryFile:
    for _tmp in summaryLines:
      outputSummaryFile.write(_tmp+'\n')

  if verbosity >= 0:
    if numWorkflowsWithDiffs > 0:
      print('TriggerResults: found differences in {:d} / {:d} workflows'.format(numWorkflowsWithDiffs, len(ret.keys())))
    else:
      print('TriggerResults: no differences found')

#### main
if __name__ == '__main__':
    ### args
    parser = argparse.ArgumentParser(prog='./'+os.path.basename(__file__), formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)

    parser.add_argument('-r', '--reference-dir', dest='inputDir_refe', action='store', default=None, required=True,
                        help='path to directory with baseline (or, "reference") workflow outputs')

    parser.add_argument('-t', '--target-dir', dest='inputDir_targ', action='store', default=None, required=True,
                        help='path to directory with new (or, "target") workflow outputs')

    parser.add_argument('-f', '--file-pattern', dest='file_pattern', action='store', default='step*.root',
                        help='basename pattern of input EDM files to be compared')

    parser.add_argument('-o', '--output-dir', dest='outputDir', action='store', default=None, required=True,
                        help='path to output directory')

    parser.add_argument('-m', '--max-events', dest='max_events', action='store', type=int, default=-1,
                        help='maximum number of events considered per comparison (default: -1, i.e. all)')

    parser.add_argument('-d', '--dry-run', dest='dry_run', action='store_true', default=False,
                        help='enable dry-run mode')

    parser.add_argument('-v', '--verbosity', dest='verbosity', type=int, default=0,
                        help='level of verbosity')

    opts, opts_unknown = parser.parse_known_args()
    ### -------------------------

    # check: unrecognized command-line arguments
    if len(opts_unknown) > 0:
      KILL('unrecognized command-line arguments: '+str(opts_unknown))

    # check: input directories
    if not os.path.isdir(opts.inputDir_refe):
      KILL('invalid path to directory with baseline (or, "reference") workflow outputs [-r]: '+opts.inputDir_refe)

    if not os.path.isdir(opts.inputDir_targ):
      KILL('invalid path to directory with new (or, "target") workflow outputs [-t]: '+opts.inputDir_targ)

    # check: output
    outDir = opts.outputDir
    if os.path.exists(outDir):
      KILL('target output directory already exists [-o]: '+outDir)
      outDir = None

    # check: external dependencies
    if which('edmDumpEventContent', permissive=True) is None:
      KILL('executable "edmDumpEventContent" is not available (set up an appropriate CMSSW area)')

    if which('hltDiff', permissive=True) is None:
      KILL('executable "hltDiff" is not available (set up an appropriate CMSSW area)')

    # run TriggerResults comparisons
    compareTriggerResults(**{
      'inputDir1': opts.inputDir_refe,
      'inputDir2': opts.inputDir_targ,
      'filePattern': opts.file_pattern,
      'maxEvents': opts.max_events,
      'outputDir': outDir,
      'dryRun': opts.dry_run,
      'verbosity': opts.verbosity,
    })
