#!/bin/bash -ex
#  vars set because some functions are using them
INSTALL_PATH=$1
SCRAM_ARCH=$2
RPMS_REPO=$3
PACKAGE_NAME=$4
REINSTALL=$5
export LC_ALL=C
export LC_CTYPE=C
export LANG=C
if [ -z "$1" ] || [ -z "$2" ] || [ -z "$3" ] || [ -z "$4" ] ; then
    echo "Usage: $0 INSTALL_DIR SCRAM_ARCH RPMS_REPO PACKAGE_NAME [REINSTALL:true|false]"
    exit 1
fi

#make sure area is bootstraped
CMS_BOT_DIR=$(cd $(dirname $0)/..; /bin/pwd -P)
${CMS_BOT_DIR}/cvmfs_deployment/bootstrap_dir_for_arch.sh ${INSTALL_PATH} ${SCRAM_ARCH} ${RPMS_REPO}

source ${CMS_BOT_DIR}/dockerrun.sh
CMSPKG="${INSTALL_PATH}/common/cmspkg -a ${SCRAM_ARCH}"
if [ $(echo "${SCRAM_ARCH}" | grep '^slc' | wc -l) -gt 0 ] ; then
    RPM_CONFIG=${INSTALL_PATH}/${SCRAM_ARCH}/var/lib/rpm/DB_CONFIG
    if [ ! -e ${RPM_CONFIG} ] ; then
        echo "WARNING: For now ignore fixing mutex_set_max"
        #echo "mutex_set_max 10000000" > $RPM_CONFIG
        #dockerrun "${CMSPKG} env -- rpmdb --rebuilddb"
    fi
fi

CMSPKG_OPTS=""
[ "${REINSTALL}" = true ] && CMSPKG_OPTS="--reinstall"

dockerrun "${CMSPKG} ${CMSPKG_OPTS} install ${CMSPKG_ARGS} -y ${PACKAGE_NAME}"
if [ "$LOCK_CVMFS" != "false" ] ; then 
  BOOK_KEEPING="/cvmfs/${CVMFS_REPOSITORY}/cvmfs-cms.cern.ch-updates"
  touch ${BOOK_KEEPING}
  BOOK_KEEPING_PKG="${PACKAGE_NAME}"
  if [ "${PACKAGE_NAME}" = "cms+cms-common+1.0" ] ; then
    BOOK_KEEPING_PKG="${PACKAGE_NAME}+${CMS_COMMON_REVISION}"
  fi
  echo "${BOOK_KEEPING_PKG} ${SCRAM_ARCH} $(date +%s) $(date)" >> ${BOOK_KEEPING}
fi
