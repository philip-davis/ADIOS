#!/usr/bin/env python
import sys
import os
import argparse

import adios
import skelconf
import skel_settings


def generate_c (outfile, config, params, test):
    if test.get_type() == 'write':
        generate_c_write (outfile, config, params, test)
    elif test.get_type() == 'read_all':
        generate_c_read_all (outfile, config, params, test)


def generate_fortran (outfile, config, params, test):
    if test.get_type() == 'write':
        generate_fortran_write (outfile, config, params, test)
    elif test.get_type() == 'read_all':
        generate_c_read_all (outfile, config, params, test)

def generate_c_write (outfile, config, params, test):
    
    outfile = outfile.replace ('.c', '_write.c')
    measure = test.get_measure()

    #print 'opening ' + outfile
    c_file = open (outfile, 'w')

    # Look at all of the groups, Generate the code when we find the requested group
    # The loop is left over from a previous iteration, it could very well be removed.
    for g in config.get_groups():

        # if a group was specified, and this is not it, go to the next group
        if g.get_name() != test.get_group_name():
            continue

        c_file.write ('//\n// Automatically generated by skel. Modify at your own risk.\n')

        # Generate includes
        c_file.write ('\n#include "adios.h"')
        c_file.write ('\n#include "mpi.h"')
        c_file.write ('\n#include "skel/skel_xml_output.h"')
        c_file.write ('\n#include <stdlib.h>')
        c_file.write ('\n#include <stdio.h>')

        c_file.write ('\n\nint main (int argc, char ** argv)')
        c_file.write ('\n{')


        c_file.write ('\n\nMPI_Init (&argc, &argv);')

        # Declare timers
        c_file.write ('\n\ndouble skel_init_timer = 0;')
        c_file.write ('\ndouble skel_open_timer = 0;')
        c_file.write ('\ndouble skel_access_timer = 0;')
        c_file.write ('\ndouble skel_close_timer = 0;')
        c_file.write ('\ndouble skel_total_timer = 0;')

        c_file.write ('\n\n// Time the init')
        c_file.write ('\nMPI_Barrier (MPI_COMM_WORLD);')
        c_file.write ('\nskel_init_timer -= MPI_Wtime();')

        c_file.write ('\n\nadios_init ("' + config.get_filename() + '");')

        c_file.write ('\nskel_init_timer += MPI_Wtime();')

        c_file.write ('\n\nint skel_mpi_size, skel_mpi_rank, skel_i;')
        c_file.write ('\nuint64_t adios_groupsize;')
        c_file.write ('\nMPI_Comm_rank (MPI_COMM_WORLD, &skel_mpi_rank);')
        c_file.write ('\nMPI_Comm_size (MPI_COMM_WORLD, &skel_mpi_size);')

        c_file.write ('\n\nint64_t adios_handle;')
        c_file.write ('\nuint64_t skel_total_size;')


        # Declare all of the program variables
        # We split the scalars and the arrays, since the arrays will likely depend on some of
        # the scalars having already been declared.
        # The sets are used to eliminate duplicates when multiple file vars are written from the
        # same program var (as is done by genarray)
        c_file.write ('\n\n// Scalar declarations')
        declarations = set()
        for v in filter (lambda x : x.is_scalar(), g.get_vars() ):
            declarations.add (adios.cFormatter.get_declaration (v, params.get_group (g.get_name() ) ) )

        for d in declarations:
            c_file.write (d)

        # Now the initializations
        for v in filter (lambda x : x.is_scalar(), g.get_vars() ):
            c_file.write (adios.cFormatter.get_initialization (v, params.get_group (g.get_name() ) ) )

        c_file.write ('\n\n// Array declarations')
        declarations = set()
        for v in filter (lambda x : not x.is_scalar(), g.get_vars() ):
            declarations.add (adios.cFormatter.get_declaration (v, params.get_group (g.get_name() ) ) )

        for d in declarations:
            c_file.write ('\n' + d)

        for v in filter (lambda x : not x.is_scalar(), g.get_vars() ):
            c_file.write (adios.cFormatter.get_initialization (v, params.get_group (g.get_name() ) ) )

        if measure.use_sleep_before_open():
            c_file.write ('\n\nsleep(30);')


        #Loop <steps> times
        c_file.write ('\n\nfor (skel_i = 0; skel_i < ' + test.get_steps() + '; skel_i++)' )
        c_file.write ('{')

        #start timing
        c_file.write ('\n\n// Time the opens')
        if measure.use_barrier_before_open():
            c_file.write ('\nMPI_Barrier (MPI_COMM_WORLD);')
        c_file.write ('\nskel_open_timer -= MPI_Wtime();')
        c_file.write ('\nskel_total_timer -= MPI_Wtime();')

        c_file.write ('\nMPI_Comm comm = MPI_COMM_WORLD;')

        c_file.write ('\nadios_open(&adios_handle, "' + g.get_name() + '", "out_' + test.get_group_name() + '_' + test.get_type() + '.bp", "w", comm);')

        #end timing
        c_file.write ('\nskel_open_timer += MPI_Wtime();')

        # Generate the write statements
        c_file.write ('\n\n// Time the writes')
        if measure.use_barrier_before_access():
            c_file.write ('\nMPI_Barrier (MPI_COMM_WORLD);')
        c_file.write ('\nskel_access_timer -= MPI_Wtime();')

        # Set the adios group size
        c_file.write (adios.cFormatter.get_groupsize_code (g) )

        c_file.write ('\n\n// Write each variable')
        for v in g.get_vars():
            c_file.write (adios.cFormatter.get_write_line (v) )

        c_file.write ('\n\n// Stop timing the writes')
        c_file.write ('\nskel_access_timer += MPI_Wtime();')
            
        # close the file
        c_file.write ('\n\n// Time the closes')
        if measure.use_barrier_before_close():
            c_file.write ('\nMPI_Barrier (MPI_COMM_WORLD);')
        c_file.write ('\nskel_close_timer -= MPI_Wtime();')
        c_file.write ('\nadios_close (adios_handle);')
        if measure.use_barrier_after_close():
            c_file.write ('\nMPI_Barrier (MPI_COMM_WORLD);')
        c_file.write ('\nskel_close_timer += MPI_Wtime();')

        #<steps> loop ends here
        c_file.write('}')

        if measure.use_barrier_before_final_time():
            c_file.write ('\nMPI_Barrier (MPI_COMM_WORLD);')

        c_file.write ('\nskel_total_timer += MPI_Wtime();')


        # Output timing info
        # For now, do a reduce to output a single value for the total time
        # In future we can gather and output all of the times to see variability
        c_file.write ('\n\n// Output results')

        if measure.use_adios_timing():

            c_file.write ('\n\n adios_timing_write_xml (adios_handle, "' + params.get_application() + '_skel_time.xml");')

        else:
            c_file.write ('\n\n skel_write_coarse_xml_data ();')


        c_file.write ('\ndouble skel_total_init, skel_total_open, skel_total_access, skel_total_close, skel_total_total;')

        if measure.use_reduce():
            c_file.write ('\nMPI_Reduce (&skel_init_timer, &skel_total_init, 1, MPI_DOUBLE, MPI_MAX, 0, MPI_COMM_WORLD);')
            c_file.write ('\nMPI_Reduce (&skel_open_timer, &skel_total_open, 1, MPI_DOUBLE, MPI_MAX, 0, MPI_COMM_WORLD);')
            c_file.write ('\nMPI_Reduce (&skel_access_timer, &skel_total_access, 1, MPI_DOUBLE, MPI_MAX, 0, MPI_COMM_WORLD);')
            c_file.write ('\nMPI_Reduce (&skel_close_timer, &skel_total_close, 1, MPI_DOUBLE, MPI_MAX, 0, MPI_COMM_WORLD);')
            c_file.write ('\nMPI_Reduce (&skel_total_timer, &skel_total_total, 1, MPI_DOUBLE, MPI_MAX, 0, MPI_COMM_WORLD);')
#        else:
#            c_file.write ('\nskel_total_init = skel_init_timer;')
#            c_file.write ('\nskel_total_open = skel_open_timer;')
#            c_file.write ('\nskel_total_access = skel_access_timer;')
#            c_file.write ('\nskel_total_close = skel_close_timer;')
#            c_file.write ('\nskel_total_total = skel_total_timer;')



# Need to check whether A, compiled with timing support, and B, timing enabled.
# If A and B, skip other reporting and use adios_timing, otherwise produce xml here.



        if measure.use_adios_timing():
            print "Use adios timing"
        else:
            print "Don't use adios timing"


            # Detailed reporting disabled, use adios timing instead.

            #c_file.write ('\n    fprintf (stdout, "rank, %i, open: %f, access %f, close %f, total %f\\n", skel_mpi_rank, skel_open_timer, skel_access_timer, skel_close_timer, skel_total_timer);')
            #c_file.write ('\n    fprintf (stdout, "effective bandwidth %f, adios_groupsize %lli\\n", adios_groupsize * skel_mpi_size / (skel_total_total * (1024 * 1024 * 1024) ), adios_groupsize);')
            

        c_file.write ('\nif (skel_mpi_rank == 0) {')

        #c_file.write ('\n    fprintf (stdout, "RRR rank, %i, open: %f, access %f, close %f, total %f\\n", skel_mpi_rank, skel_total_open, skel_total_access, skel_total_close, skel_total_total);')
        #c_file.write ('\n    fprintf (stdout, "RRR effective bandwidth %f, adios_groupsize %lli\\n", adios_groupsize * skel_mpi_size / (skel_total_total * (1024 * 1024 * 1024) ), adios_groupsize);')

        c_file.write ('\n    fprintf (stdout, "\\n");')
        c_file.write ('\n    fprintf (stdout, "\\n*************************");')
        c_file.write ('\n    fprintf (stdout, "\\n   Groupsize: %lli", adios_groupsize);')
        c_file.write ('\n    fprintf (stdout, "\\n  Open Time: %f", skel_total_open);')
        c_file.write ('\n    fprintf (stdout, "\\nAccess Time: %f", skel_total_access);')
        c_file.write ('\n    fprintf (stdout, "\\n Close Time: %f", skel_total_close);')
        c_file.write ('\n    fprintf (stdout, "\\n Total Time: %f", skel_total_total);')
        c_file.write ('\n    fprintf (stdout, "\\n*************************");')
        c_file.write ('\n    fprintf (stdout, "\\n");')


        c_file.write ('\n}')
        

        # free the array memory
        c_file.write ('\n\n// Free the arrays')
        frees = set()
        for v in filter (lambda x : not x.is_scalar(), g.get_vars() ):
            frees.add ('\nfree (' + v.get_gwrite() + ');')

        for f in frees:
            c_file.write (f)

        c_file.write ('\n\n// Clean up')

        c_file.write ('\nadios_finalize(0);')

        c_file.write ('\nMPI_Finalize();')
        c_file.write ('\n}\n')

        # Just write one group, so if we get here, we are finished 
        break

    c_file.close()

    # end: generate_c_write


def generate_fortran_write (outfile, config, params, test):

    outfile = outfile.replace ('.f90', '_write.f90')
    measure = test.get_measure()

    f_file = open (outfile, 'w')

    # Look at all of the groups, Generate the code when we find the requested group
    # The loop is left over from a previous iteration, it could very well be removed.
    for g in config.get_groups():

        # if a group was specified, and this is not it, go to the next group
        if g.get_name() != test.get_group_name():
            continue

        f_file.write ('!!\n!! Automatically generated by skel. Modify at your own risk.\n')

        f_file.write ('\n\nprogram skel')
        f_file.write ('\n')
        

        # Generate includes
        f_file.write ('\n\n  use mpi')

        f_file.write ('\n  IMPLICIT NONE')


        # Declare timers
        f_file.write ('\n\n  real*8 :: skel_init_timer = 0, &')
        f_file.write ('\n    skel_open_timer = 0, &')
        f_file.write ('\n    skel_access_timer = 0, &')
        f_file.write ('\n    skel_close_timer = 0, &')
        f_file.write ('\n    skel_total_timer = 0')

        f_file.write ('\n\n  CHARACTER(LEN=128) :: skel_filename')
        f_file.write ('\n\n  integer*4 :: skel_mpi_size, skel_mpi_rank, skel_i')
        f_file.write ('\n  integer*4 :: error')
        f_file.write ('\n  integer*8 :: adios_error')

        f_file.write ('\n  integer*8 :: adios_groupsize')

        f_file.write ('\n\n  integer :: comm')

        f_file.write ('\n\n  integer*8 :: adios_handle, &')
        f_file.write ('\n    skel_total_size')

        f_file.write ('\n  real*8 :: skel_total_init, skel_total_open, skel_total_access, skel_total_close, skel_total_total')


        # Declare all of the program variables
        # We split the scalars and the arrays, since the arrays will likely depend on some of
        # the scalars having already been declared.
        # The sets are used to eliminate duplicates when multiple file vars are written from the
        # same program var (as is done by genarray)
        f_file.write ('\n\n! Scalar declarations')
        declarations = set()
        for v in filter (lambda x : x.is_scalar(), g.get_vars() ):
            declarations.add (adios.fortranFormatter.get_declaration (v, params.get_group (g.get_name() ) ) )

        for d in declarations:
            f_file.write (d)

        f_file.write ('\n\n! Array declarations')
        declarations = set()
        for v in filter (lambda x : not x.is_scalar(), g.get_vars() ):
            declarations.add (adios.fortranFormatter.get_declaration (v, params.get_group (g.get_name() ) ) )

        for d in declarations:
            f_file.write (d)




        f_file.write ('\n\n  call MPI_INIT (error)')

        f_file.write ('\n\n! Time the init')
        f_file.write ('\n  call MPI_BARRIER (MPI_COMM_WORLD, error)')
        f_file.write ('\n  skel_init_timer = skel_init_timer - MPI_Wtime();')

        f_file.write ('\n\n  call adios_init ("' + config.get_filename() + '", MPI_COMM_WORLD, adios_error)')

        f_file.write ('\n  skel_init_timer = skel_init_timer + MPI_WTIME();')

        f_file.write ('\n  call MPI_Comm_rank (MPI_COMM_WORLD, skel_mpi_rank, error)')
        f_file.write ('\n  call MPI_Comm_size (MPI_COMM_WORLD, skel_mpi_size, error)')


        f_file.write ('\n\n! Initialize the scalars')

        # Now the scalar initializations
        # Need to worry about the order of these since some will be used by others
        # For now, just do the numerical values first, then come back and do the more
        # complicated ones. This won't cover something like a depends on b, b depends on c,
        # but it will work for the moment
        for v in filter (lambda x : x.is_scalar(), g.get_vars() ):
            #split at the spaces, just print the ones where the third element is a number
            init_str = adios.fortranFormatter.get_initialization (v, params.get_group (g.get_name() ) )
            if init_str.split (None, 2)[2].isdigit():
                f_file.write (init_str)

        for v in filter (lambda x : x.is_scalar(), g.get_vars() ):
            #split at the spaces, just print the ones where the third element is a number
            init_str = adios.fortranFormatter.get_initialization (v, params.get_group (g.get_name() ) )
            if not init_str.split (None, 2)[2].isdigit():
                f_file.write (init_str)

        f_file.write ('\n\n! Initialize the arrays')

		# And the vector initializations
        for v in filter (lambda x : not x.is_scalar(), g.get_vars() ):
            f_file.write (adios.fortranFormatter.get_initialization (v, params.get_group (g.get_name() ) ) )


        if measure.use_sleep_before_open():
            f_file.write ('\n\n  call sleep (30)')
        #start timing
        f_file.write ('\n  skel_total_timer = skel_total_timer - MPI_Wtime()')

        f_file.write ('\n\n skel_i = 0')

        #Loop <steps> times
        f_file.write ('\n\n DO')
        f_file.write ('\n  skel_i = skel_i + 1')
        f_file.write ('\n  IF (skel_i .GT. ' + test.get_steps() + ') EXIT')

        f_file.write ('\n\n! Time the opens')
        if measure.use_barrier_before_open():
            f_file.write ('\n  call MPI_Barrier (MPI_COMM_WORLD, error)')
        f_file.write ('\n  skel_open_timer = skel_open_timer - MPI_Wtime()')

        #f_file.write ('\n  MPI_Comm comm = MPI_COMM_WORLD;')

        f_file.write ('\n\n  write (skel_filename, \'(I0)\') skel_i')
        f_file.write ('\n  skel_filename = "out_' + test.get_group_name() + '_' + test.get_type() + '_"//skel_filename//".bp"')

        f_file.write ('\n call MPI_Comm_dup (MPI_COMM_WORLD, comm, error)')

        f_file.write ('\n  call adios_open(adios_handle, "' + g.get_name() + '", skel_filename, "w", comm, adios_error);')

        #end timing
        f_file.write ('\n  skel_open_timer = skel_open_timer + MPI_Wtime()')

        # Generate the write statements
        f_file.write ('\n\n! Time the writes')
        if measure.use_barrier_before_access():
            f_file.write ('\n  call MPI_Barrier (MPI_COMM_WORLD, error)')
        f_file.write ('\n  skel_access_timer = skel_access_timer - MPI_Wtime()')

        # Set the adios group size
        f_file.write (adios.fortranFormatter.get_groupsize_code (g) )

        f_file.write ('\n\n! Write each variable')
        for v in g.get_vars():
            f_file.write (adios.fortranFormatter.get_write_line (v) )

        f_file.write ('\n\n! Stop timing the writes')
        f_file.write ('\n  skel_access_timer = skel_access_timer + MPI_Wtime()')
            
        # close the file
        f_file.write ('\n\n! Time the closes')
        if measure.use_barrier_before_close():
            f_file.write ('\n  call MPI_Barrier (MPI_COMM_WORLD, error)')
        f_file.write ('\n  skel_close_timer = skel_close_timer - MPI_Wtime()')
        f_file.write ('\n  call adios_close (adios_handle, adios_error)')
        if measure.use_barrier_after_close():
            f_file.write ('\n  call MPI_Barrier (MPI_COMM_WORLD, error)')
        f_file.write ('\n  skel_close_timer = skel_close_timer + MPI_Wtime()')

        f_file.write ('\n\n END DO')

        if measure.use_barrier_before_final_time():
            f_file.write ('\n\n  call MPI_Barrier (MPI_COMM_WORLD, error)')
        f_file.write ('\n\n  skel_total_timer = skel_total_timer + MPI_Wtime()')

        # Output timing info
        # For now, do a reduce to output a single value for the total time
        # In future we can gather and output all of the times to see variability
        f_file.write ('\n\n! Output results')

        if measure.use_adios_timing():
            f_file.write ('\n\n  call adios_timing_write_xml (adios_handle, "' + params.get_application() + '_skel_time.xml")')
        else:
            f_file.write ('\n\n  call skel_write_coarse_xml_data_f (skel_open_timer, skel_access_timer, skel_close_timer, skel_total_timer)')
            
        if measure.use_reduce():
            f_file.write ('\n\n  call MPI_Reduce (skel_init_timer, skel_total_init, 1, MPI_DOUBLE_PRECISION, MPI_MAX, 0, MPI_COMM_WORLD, error)')
            f_file.write ('\n  call MPI_Reduce (skel_open_timer, skel_total_open, 1, MPI_DOUBLE_PRECISION, MPI_MAX, 0, MPI_COMM_WORLD, error)')
            f_file.write ('\n  call MPI_Reduce (skel_access_timer, skel_total_access, 1, MPI_DOUBLE_PRECISION, MPI_MAX, 0, MPI_COMM_WORLD, error)')
            f_file.write ('\n  call MPI_Reduce (skel_close_timer, skel_total_close, 1, MPI_DOUBLE_PRECISION, MPI_MAX, 0, MPI_COMM_WORLD, error)')
            f_file.write ('\n  call MPI_Reduce (skel_total_timer, skel_total_total, 1, MPI_DOUBLE_PRECISION, MPI_MAX, 0, MPI_COMM_WORLD, error)')
        else:
            f_file.write ('\n  skel_total_init = skel_init_timer')
            f_file.write ('\n  skel_total_open = skel_open_timer')
            f_file.write ('\n  skel_total_access = skel_access_timer')
            f_file.write ('\n  skel_total_close = skel_close_timer')
            f_file.write ('\n  skel_total_total = skel_total_timer')

            # All rank reporting disabled for skel, use ADIOS timing library instead.

            #f_file.write ('\n    fprintf (stdout, "rank, %i, open: %f, access %f, close %f, total %f\\n", skel_mpi_rank, skel_open_timer, skel_access_timer, skel_close_timer, skel_total_timer);')
            #f_file.write ("\n\n  write (*,'(a6,i7,a7,f15.8,a9,f15.8,a7,f15.8,a7,f15.8)') 'rank, ', skel_mpi_rank , ' open: ', skel_open_timer, ', access ', skel_access_timer, ' close ', skel_close_timer, ' total ', skel_total_timer")
            #f_file.write ('\n    fprintf (stdout, "effective bandwidth %f, adios_groupsize %lli\\n", adios_groupsize * skel_mpi_size / (skel_total_total * (1024 * 1024 * 1024) ), adios_groupsize);')
            #f_file.write ("\n  write (*, '(a20,f15.8,a17,i9)') 'effective bandwidth ', adios_groupsize * skel_mpi_size / (skel_total_total * (1024 * 1024 * 1024) ), 'adios_groupsize: ', adios_groupsize")
            

        f_file.write ('\n\n  if (skel_mpi_rank == 0) then')

        f_file.write ("\n    write (*,*) '\\n'")
        f_file.write ("\n    write (*,*) '**************************'")
        f_file.write ("\n    write (*,*) '  Groupsize: ', adios_groupsize")
        f_file.write ("\n    write (*,*) '  Open Time: ', skel_total_open")
        f_file.write ("\n    write (*,*) 'Access Time: ', skel_total_access")
        f_file.write ("\n    write (*,*) ' Close Time: ', skel_total_close")
        f_file.write ("\n    write (*,*) ' Total Time: ', skel_total_total")
        f_file.write ("\n    write (*,*) '**************************'")
        f_file.write ("\n    write (*,*) '\\n'")

        #f_file.write ("\n    write (*, '(a10,i9,a7,f15.8,a8,f15.8,a7,f15.8,a7,f15.8,a2)')  'RRR rank, ', skel_mpi_rank, ' open: ', skel_total_open, ' access ', skel_total_access, ' close ', skel_total_close, ' total ', skel_total_total, '\\n'")

        #f_file.write ("\n    write (*,'(a24,f15.8,a17,i9)') 'RRR effective bandwidth ', adios_groupsize * skel_mpi_size / (skel_total_total * (1024 * 1024 * 1024) ), 'adios_groupsize', adios_groupsize")

        f_file.write ('\n  endif')
        

        # free the array memory -- skip this for now
        #f_file.write ('\n\n// Free the arrays')
        #frees = set()
        #for v in filter (lambda x : not x.is_scalar(), g.get_vars() ):
        #    frees.add ('\nfree (' + v.get_gwrite() + ');')

        #for f in frees:
        #    f_file.write (f)

        f_file.write ('\n\n! Clean up')

        f_file.write ('\n  call adios_finalize(0, adios_error)')

        f_file.write ('\n  call MPI_Finalize(error)')
        f_file.write ('\n\nend program skel\n')

        # Just write one group, so if we get here, we are finished 
        break

    f_file.close()

    # end: generate_fortran_write


# Needs to be updated to use new read API
def generate_c_read_all (outfile, config, params, test):

    outfile = outfile.replace ('.c', '_read_all.c')

    c_file = open (outfile, 'w')

    # Look at all of the groups, Generate the code when we find the requested group
    # The loop is left over from a previous iteration, it could very well be removed.
    for g in config.get_groups():

        # if a group was specified, and this is not it, go to the next group
        if g.get_name() != test.get_group_name():
            continue

        c_file.write ('//\n// Automatically generated by skel. Modify at your own risk.\n')

        # Generate includes
        c_file.write ('\n#include "adios.h"')
        c_file.write ('\n#include "adios_read.h"')
        c_file.write ('\n#include "mpi.h"')
        c_file.write ('\n#include <stdlib.h>')
        c_file.write ('\n#include <stdio.h>')

        c_file.write ('\n\nint main (int argc, char ** argv)')
        c_file.write ('\n{')

        c_file.write ('\n\nMPI_Init (&argc, &argv);')
        c_file.write ('\nadios_init ("' + config.get_filename() + '", MPI_COMM_WORLD);')

        c_file.write ('\nint skel_mpi_size, skel_mpi_rank, skel_i;')
        c_file.write ('\nMPI_Comm_rank (MPI_COMM_WORLD, &skel_mpi_rank);')
        c_file.write ('\nMPI_Comm_size (MPI_COMM_WORLD, &skel_mpi_size);')

        # Declare timers
        c_file.write ('\n\ndouble skel_open_timer = 0;')
        c_file.write ('\ndouble skel_access_timer = 0;')
        c_file.write ('\ndouble skel_close_timer = 0;')

        # Declare all of the program variables
        # We split the scalars and the arrays, since the arrays will likely depend on some of
        # the scalars having already been declared.
        # The sets are used to eliminate duplicates when multiple file vars are written from the
        # same program var (as is done by genarray)
        c_file.write ('\n\n// Scalar declarations')
        declarations = set()
        for v in filter (lambda x : x.is_scalar(), g.get_vars() ):
            declarations.add (adios.cFormatter.get_declaration (v, params.get_group (g.get_name() ) ) )

        for d in declarations:
            c_file.write (d)

        c_file.write ('\n\n// Array declarations')
        declarations = set()
        for v in filter (lambda x : not x.is_scalar(), g.get_vars() ):
            declarations.add (adios.cFormatter.get_declaration (v, params.get_group (g.get_name() ) ) )

        for d in declarations:
            c_file.write ('\n' + d)

        #start timing
        c_file.write ('\n\n// Time the opens')
        c_file.write ('\nMPI_Barrier (MPI_COMM_WORLD);')
        c_file.write ('\nskel_open_timer -= MPI_Wtime();')

        c_file.write ('\nMPI_Comm comm = MPI_COMM_WORLD;')

        c_file.write ('\nADIOS_FILE* afile = adios_fopen ("out_' + test.get_group_name() + '_' + test.get_type() + '.bp", comm);')
        c_file.write ('\nADIOS_GROUP* group = adios_gopen (afile, "' + g.get_name() + '");')

        #end timing
        c_file.write ('\nskel_open_timer += MPI_Wtime();')

        # Generate the write statements
        c_file.write ('\n\n// Time the writes')
        c_file.write ('\nMPI_Barrier (MPI_COMM_WORLD);')
        c_file.write ('\nskel_access_timer -= MPI_Wtime();')

        c_file.write ('\n\n// Read all of each variable')
        c_file.write ('\nuint64_t starts[] = {0,0,0,0,0,0,0,0}; // 8 dimensions should do it.')
        c_file.write ('\nuint64_t counts[] = {0,0,0,0,0,0,0,0};')

        for v in g.get_vars():

            c_file.write ('\n')

            # The tricky bit here is deciding whether we need the & before the variable name.
            # We omit it in two cases: 1) the variable type is string, or 2) the variable is not a scalar
            if (v.get_c_type() == 'string' or v.get_dimensions() != None):
                var_prefix = ''
            else:
                var_prefix = '&'
        
            index = 0
            if v.get_dimensions() != None:
                for d in v.get_dimensions():
                    c_file.write ('\ncounts[%d] = '% index + d + ';')
                    index = index + 1

            c_file.write ('\nadios_read_var(group, "' + v.get_name() + '", starts, counts, ' + var_prefix + v.get_gwrite() + ');' )

        c_file.write ('\n\n// Stop timing the writes')
        c_file.write ('\nskel_access_timer += MPI_Wtime();')
            
        # close the file
        c_file.write ('\n\n// Time the closes')
        c_file.write ('\nMPI_Barrier (MPI_COMM_WORLD);')
        c_file.write ('\nskel_close_timer -= MPI_Wtime();')
        c_file.write ('\nadios_gclose (group);')
        c_file.write ('\nadios_fclose (afile);')
        c_file.write ('\nskel_close_timer += MPI_Wtime();')


        # Output timing info
        # For now, do a reduce to output a single value for the total time
        # In future we can gather and output all of the times to see variability
        c_file.write ('\n\n// Output results')
        c_file.write ('\ndouble skel_total_open, skel_total_access, skel_total_close;')
        c_file.write ('\nMPI_Reduce (&skel_open_timer, &skel_total_open, 1, MPI_DOUBLE, MPI_MAX, 0, MPI_COMM_WORLD);')
        c_file.write ('\nMPI_Reduce (&skel_access_timer, &skel_total_access, 1, MPI_DOUBLE, MPI_MAX, 0, MPI_COMM_WORLD);')
        c_file.write ('\nMPI_Reduce (&skel_close_timer, &skel_total_close, 1, MPI_DOUBLE, MPI_MAX, 0, MPI_COMM_WORLD);')
        c_file.write ('\nif (skel_mpi_rank == 0) {')

        c_file.write ('\n    fprintf (stdout, "open: %f, access %f, close %f", skel_total_open, skel_total_access, skel_total_close);')

        c_file.write ('\n}')
        

        # free the array memory
        c_file.write ('\n\n// Free the arrays')
        frees = set()
        for v in filter (lambda x : not x.is_scalar(), g.get_vars() ):
            frees.add ('\nfree (' + v.get_gwrite() + ');')

        for f in frees:
            c_file.write (f)

        c_file.write ('\n\n// Clean up')

        c_file.write ('\nadios_finalize(0);')

        c_file.write ('\nMPI_Finalize();')
        c_file.write ('\n}\n')

        # Just write one group, so if we get here, we are finished 
        break

    c_file.close()

    #end: generate_c_read_all



def create_sources (params, config, project):

    # Determine the target language
    if config.host_language == "C" or config.host_language =="c":
        generate = generate_c
        filetype = ".c"
    else:
        generate = generate_fortran
        filetype = ".f90"

    # Produce all of the Fortran files
    for batch in params.get_batches():
        for test in batch.get_tests():

            # Determine outfile name
            extension = '_skel_' + test.get_group_name()
            outfilename = project + extension + filetype

            generate (outfilename, config, params, test)



def parse_command_line():

    parser = argparse.ArgumentParser (description='Generate the required source code for the specified skel project')
    parser.add_argument ('project', metavar='project', help='Name of the skel project')

    return parser.parse_args()



def main(argv=None):

    skel_settings.create_settings_dir_if_needed()

    args = parse_command_line()

    config = adios.adiosConfig (args.project + '_skel.xml')
    params = skelconf.skelConfig (args.project + '_params.xml')

    create_sources (params, config, args.project)


        

if __name__ == "__main__":
    main()

 
